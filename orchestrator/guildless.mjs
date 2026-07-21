#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { compileMission } from "./planner.mjs";
import { defaultEngines } from "./engines.mjs";

function usage() {
  console.log("Usage: node orchestrator/guildless.mjs plan <mission.json>");
}

const [, , command, missionPath] = process.argv;
if (command !== "plan" || !missionPath) {
  usage();
  process.exitCode = 1;
} else {
  const mission = JSON.parse(await readFile(missionPath, "utf8"));
  const plan = compileMission(mission, defaultEngines);
  console.log(JSON.stringify(plan, null, 2));
}
