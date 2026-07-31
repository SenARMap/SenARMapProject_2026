import { Hono } from "hono";
import { handle } from "hono/cloudflare-pages";
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

type Bindings = {
  IMAGE_BUCKET: R2Bucket;
  R2_ACCOUNT_ID: string;
  R2_BUCKET_NAME: string;
  R2_ACCESS_KEY_ID: string;
  R2_SECRET_ACCESS_KEY: string;
};

const MAX_FILES_PER_REQUEST = 2000;
const URL_EXPIRES_SECONDS = 15 * 60;

function sanitizeFilename(name: string): string {
  const base = name.split(/[\\/]/).pop() ?? "file";
  const cleaned = base.replace(/[^\w.\-ぁ-んァ-ヶ一-龠々ー]/g, "_").slice(0, 150);
  return cleaned || "file";
}

function buildObjectKey(originalName: string): string {
  const date = new Date().toISOString().slice(0, 10);
  const unique = crypto.randomUUID();
  return `uploads/${date}/${unique}_${sanitizeFilename(originalName)}`;
}

const app = new Hono<{ Bindings: Bindings }>().basePath("/api");

app.post("/upload-urls", async (c) => {
  let body: unknown;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "リクエストボディが不正なJSONです" }, 400);
  }

  const filenames = (body as { filenames?: unknown } | null)?.filenames;
  if (!Array.isArray(filenames) || filenames.length === 0) {
    return c.json({ error: "filenames は空でない配列で指定してください" }, 400);
  }
  if (filenames.length > MAX_FILES_PER_REQUEST) {
    return c.json(
      { error: `1回のリクエストにつき filenames は最大 ${MAX_FILES_PER_REQUEST} 件までです` },
      400,
    );
  }
  if (!filenames.every((f) => typeof f === "string" && f.length > 0 && f.length <= 300)) {
    return c.json({ error: "filenames の各要素は1〜300文字の文字列である必要があります" }, 400);
  }

  const { R2_ACCOUNT_ID, R2_BUCKET_NAME, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY } = c.env;
  if (!R2_ACCOUNT_ID || !R2_BUCKET_NAME || !R2_ACCESS_KEY_ID || !R2_SECRET_ACCESS_KEY) {
    return c.json({ error: "サーバー側のR2認証情報が未設定です" }, 500);
  }

  const s3 = new S3Client({
    region: "auto",
    endpoint: `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
    credentials: {
      accessKeyId: R2_ACCESS_KEY_ID,
      secretAccessKey: R2_SECRET_ACCESS_KEY,
    },
  });

  // Presigned URL の発行はネットワーク通信を伴わない署名計算のみなので、
  // 数百〜数千件でも Promise.all で並列生成して問題ない。
  const uploads = await Promise.all(
    (filenames as string[]).map(async (filename) => {
      const key = buildObjectKey(filename);
      const command = new PutObjectCommand({ Bucket: R2_BUCKET_NAME, Key: key });
      const url = await getSignedUrl(s3, command, { expiresIn: URL_EXPIRES_SECONDS });
      return { filename, key, url };
    }),
  );

  return c.json({ uploads, expiresInSeconds: URL_EXPIRES_SECONDS });
});

export const onRequest = handle(app);
