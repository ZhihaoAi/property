import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

export const bundledNodePath = path.join(
  os.homedir(),
  ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
);

const bundledArtifactToolPath = path.join(
  os.homedir(),
  ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool"
);

export async function ensureArtifactToolLink() {
  const localLink = path.resolve("scripts/node_modules/@oai/artifact-tool");
  try {
    await fs.lstat(localLink);
    return localLink;
  } catch {}

  await fs.mkdir(path.dirname(localLink), { recursive: true });
  try {
    await fs.symlink(bundledArtifactToolPath, localLink, "dir");
  } catch (error) {
    if (error.code !== "EEXIST") {
      throw error;
    }
  }
  return localLink;
}

export async function importArtifactTool() {
  await ensureArtifactToolLink();
  return import("@oai/artifact-tool");
}
