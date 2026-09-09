import type { Context, Next } from "hono";
import { deleteCookie, getCookie, setCookie } from "hono/cookie";
import type { CookieOptions } from "hono/utils/cookie";

import { findValidSession } from "./db";
import type { AppEnv } from "./types";

export const SESSION_COOKIE = "session";
export const OAUTH_STATE_COOKIE = "oauth_state";
export const OAUTH_VERIFIER_COOKIE = "oauth_verifier";

/**
 * ローカル開発(http://localhost)ではSecure Cookieがブラウザに保存されないため、
 * リクエストのプロトコルを見てSecureフラグを切り替える。本番(Cloudflare Pages)は常にhttpsなので影響しない。
 */
function isHttps(c: Context): boolean {
  return new URL(c.req.url).protocol === "https:";
}

export function baseCookieOptions(c: Context): CookieOptions {
  return {
    httpOnly: true,
    secure: isHttps(c),
    // Google からのリダイレクトで戻ってくる際にトップレベルGETナビゲーションとして
    // Cookieが送られる必要があるため Strict ではなく Lax を使う。
    sameSite: "Lax",
    path: "/",
  };
}

export function setSessionCookie(c: Context, sessionId: string, expiresAt: Date): void {
  setCookie(c, SESSION_COOKIE, sessionId, { ...baseCookieOptions(c), expires: expiresAt });
}

export function clearSessionCookie(c: Context): void {
  deleteCookie(c, SESSION_COOKIE, { path: "/" });
}

export function setOauthCookies(c: Context, state: string, codeVerifier: string): void {
  // stateとPKCE検証用の値は認可フロー中(数分)だけ必要なので短い有効期限にする
  const opts = { ...baseCookieOptions(c), maxAge: 10 * 60 };
  setCookie(c, OAUTH_STATE_COOKIE, state, opts);
  setCookie(c, OAUTH_VERIFIER_COOKIE, codeVerifier, opts);
}

export function readAndClearOauthCookies(c: Context): { state?: string; codeVerifier?: string } {
  const state = getCookie(c, OAUTH_STATE_COOKIE);
  const codeVerifier = getCookie(c, OAUTH_VERIFIER_COOKIE);
  deleteCookie(c, OAUTH_STATE_COOKIE, { path: "/" });
  deleteCookie(c, OAUTH_VERIFIER_COOKIE, { path: "/" });
  return { state, codeVerifier };
}

/**
 * ログイン必須のAPIに付けるミドルウェア。有効なセッションが無ければ401を返す。
 * 状態を変更するリクエスト(GET以外)は、Cookie(SameSite=Lax)だけに頼らない多層防御として
 * Originヘッダが自サイトと一致するかも確認する(簡易CSRF対策)。
 */
export function requireAuth() {
  return async (c: Context<AppEnv>, next: Next) => {
    if (c.req.method !== "GET" && c.req.method !== "HEAD") {
      const origin = c.req.header("Origin");
      if (origin && origin !== new URL(c.req.url).origin) {
        return c.json({ error: "不正なリクエスト元です" }, 403);
      }
    }

    const sessionId = getCookie(c, SESSION_COOKIE);
    if (!sessionId) {
      return c.json({ error: "ログインが必要です" }, 401);
    }
    const user = await findValidSession(c.env.DB, sessionId);
    if (!user) {
      clearSessionCookie(c);
      return c.json({ error: "ログインが必要です" }, 401);
    }
    c.set("user", user);
    await next();
  };
}
