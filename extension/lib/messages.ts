import type { NewApplication, PostingRef } from '../../shared/applications';

/** Content script -> background: an application was just submitted. */
export interface LogApplicationMessage {
  type: 'log-application';
  app: NewApplication;
  ref: PostingRef | null;
}

/** Popup -> background: run Google sign-in (the popup closes when the auth window opens). */
export interface GoogleSignInMessage {
  type: 'sign-in-google';
}

/** Popup -> background: try to save queued logs now. */
export interface FlushQueueMessage {
  type: 'flush-queue';
}

export type Message = LogApplicationMessage | GoogleSignInMessage | FlushQueueMessage;

export type LogResult =
  | { ok: true; duplicate: boolean; company: string; role: string | null }
  | { ok: false; queued: true; reason: 'signed-out' | 'error'; company: string; role: string | null };

export const QUEUE_KEY = 'primora:pending-logs';
