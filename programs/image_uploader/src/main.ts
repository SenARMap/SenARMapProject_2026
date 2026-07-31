// 画像一括アップローダー: ファイル選択 → Presigned URL一括取得 → 同時実行数制限つきPUT

const REQUEST_BATCH_SIZE = 300; // /api/upload-urls 1回あたりに送るファイル名の件数

const fileInput = document.getElementById("file-input") as HTMLInputElement;
const selectionInfo = document.getElementById("selection-info") as HTMLElement;
const selectedCountEl = document.getElementById("selected-count") as HTMLElement;
const clearBtn = document.getElementById("clear-btn") as HTMLButtonElement;
const uploadBtn = document.getElementById("upload-btn") as HTMLButtonElement;
const concurrencySelect = document.getElementById("concurrency-select") as HTMLSelectElement;
const progressPanel = document.getElementById("progress-panel") as HTMLElement;
const progressCountEl = document.getElementById("progress-count") as HTMLElement;
const progressPercentEl = document.getElementById("progress-percent") as HTMLElement;
const progressBarFill = document.getElementById("progress-bar-fill") as HTMLElement;
const progressStatusEl = document.getElementById("progress-status") as HTMLElement;
const failListEl = document.getElementById("fail-list") as HTMLUListElement;

let selectedFiles: File[] = [];

fileInput.addEventListener("change", () => {
  selectedFiles = Array.from(fileInput.files ?? []);
  selectedCountEl.textContent = String(selectedFiles.length);
  selectionInfo.hidden = selectedFiles.length === 0;
  uploadBtn.disabled = selectedFiles.length === 0;
});

clearBtn.addEventListener("click", () => {
  selectedFiles = [];
  fileInput.value = "";
  selectionInfo.hidden = true;
  uploadBtn.disabled = true;
});

uploadBtn.addEventListener("click", () => {
  void startUpload();
});

/** 同時実行数を limit 件までに制限しながら tasks を全て実行する */
async function runWithConcurrencyLimit<T>(
  items: T[],
  limit: number,
  worker: (item: T, index: number) => Promise<void>,
): Promise<void> {
  let cursor = 0;
  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const index = cursor++;
      await worker(items[index], index);
    }
  });
  await Promise.all(runners);
}

type PresignedUpload = { filename: string; key: string; url: string };

async function fetchUploadUrls(filenames: string[]): Promise<PresignedUpload[]> {
  const results: PresignedUpload[] = [];
  for (let i = 0; i < filenames.length; i += REQUEST_BATCH_SIZE) {
    const batch = filenames.slice(i, i + REQUEST_BATCH_SIZE);
    const res = await fetch("/api/upload-urls", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filenames: batch }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(
        `Presigned URL取得に失敗しました (${res.status}): ${(body as { error?: string }).error ?? ""}`,
      );
    }
    const data = (await res.json()) as { uploads: PresignedUpload[] };
    results.push(...data.uploads);
    progressStatusEl.textContent = `アップロードURLを取得中… (${results.length} / ${filenames.length})`;
  }
  return results;
}

async function putFile(file: File, url: string): Promise<void> {
  const res = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": file.type || "application/octet-stream" },
    body: file,
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
}

function updateProgress(done: number, total: number, label: string): void {
  const percent = total === 0 ? 0 : Math.round((done / total) * 100);
  progressCountEl.textContent = `${done} / ${total} 件完了`;
  progressPercentEl.textContent = `${percent}%`;
  progressBarFill.style.width = `${percent}%`;
  progressStatusEl.textContent = label;
}

async function startUpload(): Promise<void> {
  if (selectedFiles.length === 0) return;

  uploadBtn.disabled = true;
  fileInput.disabled = true;
  progressPanel.hidden = false;
  failListEl.innerHTML = "";

  const total = selectedFiles.length;
  updateProgress(0, total, "アップロードURLを取得中…");

  let uploads: PresignedUpload[];
  try {
    uploads = await fetchUploadUrls(selectedFiles.map((f) => f.name));
  } catch (err) {
    progressStatusEl.textContent = `エラー: ${(err as Error).message}`;
    uploadBtn.disabled = false;
    fileInput.disabled = false;
    return;
  }

  if (uploads.length !== selectedFiles.length) {
    progressStatusEl.textContent = "エラー: サーバーから返却されたURLの件数が一致しません";
    uploadBtn.disabled = false;
    fileInput.disabled = false;
    return;
  }

  const concurrency = Number(concurrencySelect.value) || 6;
  let done = 0;
  const failures: string[] = [];

  updateProgress(0, total, "アップロード中…");

  await runWithConcurrencyLimit(selectedFiles, concurrency, async (file, index) => {
    const upload = uploads[index];
    try {
      await putFile(file, upload.url);
    } catch (err) {
      failures.push(`${file.name} (${(err as Error).message})`);
    } finally {
      done += 1;
      updateProgress(done, total, "アップロード中…");
    }
  });

  if (failures.length === 0) {
    updateProgress(total, total, "すべてのアップロードが完了しました。");
  } else {
    updateProgress(
      total,
      total,
      `完了（${failures.length}件失敗）。失敗したファイル名は下に表示しています。`,
    );
    for (const message of failures) {
      const li = document.createElement("li");
      li.textContent = message;
      failListEl.appendChild(li);
    }
  }

  uploadBtn.disabled = false;
  fileInput.disabled = false;
}
