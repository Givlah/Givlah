// Vercel: exit 0 skips a build; exit 1 proceeds. Missing history builds safely.
const {spawnSync} = require("node:child_process");
const base = process.env.VERCEL_GIT_PREVIOUS_SHA || "HEAD^";
const exists = spawnSync("git", ["cat-file", "-e", `${base}^{commit}`]);
if (exists.status !== 0) process.exit(1);
const diff = spawnSync("git", ["diff", "--quiet", base, "HEAD", "--", "."], {cwd: __dirname});
process.exit(diff.status === 0 ? 0 : 1);
