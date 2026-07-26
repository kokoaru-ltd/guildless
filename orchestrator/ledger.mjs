import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";

export class EventLedger {
  constructor(path) {
    mkdirSync(dirname(path), { recursive: true });
    this.db = new DatabaseSync(path);
    this.db.exec(`
      PRAGMA journal_mode=WAL;
      CREATE TABLE IF NOT EXISTS events (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        mission_id TEXT NOT NULL,
        type TEXT NOT NULL,
        actor TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS events_mission_seq ON events(mission_id, seq);
    `);
    this.insert = this.db.prepare(
      "INSERT INTO events (mission_id, type, actor, payload, created_at) VALUES (?, ?, ?, ?, ?)"
    );
  }

  append(missionId, type, actor, payload = {}) {
    const createdAt = new Date().toISOString();
    const result = this.insert.run(missionId, type, actor, JSON.stringify(payload), createdAt);
    return { seq: Number(result.lastInsertRowid), missionId, type, actor, payload, createdAt };
  }

  events(missionId) {
    return this.db.prepare(
      "SELECT seq, mission_id, type, actor, payload, created_at FROM events WHERE mission_id = ? ORDER BY seq"
    ).all(missionId).map(row => ({
      seq: row.seq,
      missionId: row.mission_id,
      type: row.type,
      actor: row.actor,
      payload: JSON.parse(row.payload),
      createdAt: row.created_at,
    }));
  }

  close() { this.db.close(); }
}
