import { Hono } from "hono";

import { areFriends, findUserById, listTimetable, replaceTimetable } from "../db";
import { requireAuth } from "../session";
import type { AppEnv } from "../types";
import {
  MAX_TIMETABLE_ENTRIES, validateTimetableEntry, type RawTimetableEntry,
} from "../validate";

export const timetableRoutes = new Hono<AppEnv>();

timetableRoutes.get("/", requireAuth(), async (c) => {
  const user = c.get("user");
  const entries = await listTimetable(c.env.DB, user.id);
  return c.json({ entries });
});

timetableRoutes.put("/", requireAuth(), async (c) => {
  const user = c.get("user");

  let body: unknown;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "リクエストボディが不正なJSONです" }, 400);
  }

  const entries = (body as { entries?: unknown } | null)?.entries;
  if (!Array.isArray(entries)) {
    return c.json({ error: "entries は配列で指定してください" }, 400);
  }
  if (entries.length > MAX_TIMETABLE_ENTRIES) {
    return c.json({ error: `entries は最大${MAX_TIMETABLE_ENTRIES}件までです` }, 400);
  }

  const validated = [];
  const seen = new Set<string>();
  for (const raw of entries as RawTimetableEntry[]) {
    const result = validateTimetableEntry(raw ?? {});
    if (!result.ok) {
      return c.json({ error: result.error }, 400);
    }
    const key = `${result.value.day_of_week}-${result.value.period}`;
    if (seen.has(key)) {
      return c.json({ error: `同じ曜日・時限のコマが重複しています (${key})` }, 400);
    }
    seen.add(key);
    validated.push(result.value);
  }

  await replaceTimetable(c.env.DB, user.id, validated);
  return c.json({ entries: await listTimetable(c.env.DB, user.id) });
});

// 友達の時間割を閲覧する。承諾済みの友達関係がある場合のみ許可する（サーバー側で必ず検証すること。
// フロント側の表示制御だけに頼ると、URLを直接叩かれた場合に他人の時間割が漏洩する）。
timetableRoutes.get("/friend/:userId", requireAuth(), async (c) => {
  const me = c.get("user");
  const friendId = Number(c.req.param("userId"));
  if (!Number.isInteger(friendId)) {
    return c.json({ error: "userId が不正です" }, 400);
  }
  if (friendId === me.id) {
    return c.json({ error: "自分自身は指定できません" }, 400);
  }

  const isFriend = await areFriends(c.env.DB, me.id, friendId);
  if (!isFriend) {
    return c.json({ error: "友達関係が確認できません" }, 403);
  }

  const friend = await findUserById(c.env.DB, friendId);
  if (!friend) {
    return c.json({ error: "ユーザーが見つかりません" }, 404);
  }

  const entries = await listTimetable(c.env.DB, friendId);
  return c.json({
    user: { id: friend.id, display_name: friend.display_name },
    entries,
  });
});
