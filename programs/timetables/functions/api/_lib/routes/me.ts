import { Hono } from "hono";

import { deleteUserCascade } from "../db";
import { clearSessionCookie, requireAuth } from "../session";
import type { AppEnv } from "../types";

export const meRoutes = new Hono<AppEnv>();

meRoutes.get("/", requireAuth(), (c) => {
  const user = c.get("user");
  return c.json({ id: user.id, email: user.email, display_name: user.display_name });
});

// アカウント削除。本人の全データ（セッション・時間割・友達関係）を即座に消去する。
// 個人情報を扱うサービスなので、退会導線は必ず用意しておくこと。
meRoutes.delete("/", requireAuth(), async (c) => {
  const user = c.get("user");
  await deleteUserCascade(c.env.DB, user.id);
  clearSessionCookie(c);
  return c.body(null, 204);
});
