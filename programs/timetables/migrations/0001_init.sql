-- IKU NAVI Timetables — 初期スキーマ
-- 個人情報（氏名相当の表示名・メール・時間割）を扱うため、保存する項目は必要最小限にすること。
-- 位置情報（教室名）は timetable_entries.location に任意で入るが、これは「今どこにいるか」を
-- 友達に開示することにもなるため、機能追加時は必ず docs / README のプライバシー注記を参照すること。

CREATE TABLE users (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  google_sub   TEXT NOT NULL UNIQUE,   -- Google IDトークンの sub（アカウントの不変な識別子。emailより信頼できる）
  email        TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE sessions (
  id         TEXT PRIMARY KEY,   -- セッションCookieの値そのもの（ランダムトークン。JWTではない=いつでも失効可能）
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL
);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);

CREATE TABLE timetable_entries (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  day_of_week  INTEGER NOT NULL,   -- 0=月 1=火 2=水 3=木 4=金 5=土
  period       INTEGER NOT NULL,   -- 1〜7限
  course_name  TEXT NOT NULL,
  location     TEXT,               -- 任意。教室名など（プライバシー配慮についてはREADME参照）
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(user_id, day_of_week, period)
);

-- 友達関係。承諾済みの行がそのまま「友達である」ことを表す（別テーブルに正規化しない）。
-- 相手がまだ登録していないメールアドレスにも送れるよう to_user_id は NULL 許容とし、
-- 招待された側が初めてログインした時点で to_user_id を埋める。
CREATE TABLE friend_requests (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  from_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  to_email     TEXT NOT NULL,      -- 正規化済み(小文字)のメールアドレス
  to_user_id   INTEGER REFERENCES users(id) ON DELETE CASCADE,
  status       TEXT NOT NULL DEFAULT 'pending',  -- pending | accepted
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  resolved_at  TEXT
);
CREATE INDEX idx_friend_requests_to_email ON friend_requests(to_email);
CREATE INDEX idx_friend_requests_to_user_id ON friend_requests(to_user_id);
CREATE INDEX idx_friend_requests_from_user_id ON friend_requests(from_user_id);
-- 同じ相手への保留中の招待を二重に送れないようにする（拒否/削除されたら再送可能）
CREATE UNIQUE INDEX idx_friend_requests_unique_pending
  ON friend_requests(from_user_id, to_email)
  WHERE status = 'pending';
