#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { compileMission } from "./planner.mjs";
import { defaultEngines, installedEngineSummary } from "./engines.mjs";

function usage() {
  console.log("Usage: node orchestrator/guildless.mjs <engines|plan <mission.json>>");
}

const [, , command, missionPath] = process.argv;
if (command === "engines") {
  console.log(JSON.stringify(installedEngineSummary(), null, 2));
} else if (command !== "plan" || !missionPath) {
  usage();
  process.exitCode = 1;
} else {
  const mission = JSON.parse(await readFile(missionPath, "utf8"));
  const plan = compileMission(mission, defaultEngines);
  console.log(JSON.stringify(plan, null, 2));
}
