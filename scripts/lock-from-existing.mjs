// Extract only the dependency closure used by this app from an existing lock.
// This reads local JSON only and performs no package installation or network I/O.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve, posix } from "node:path";
import { fileURLToPath } from "node:url";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = JSON.parse(
  readFileSync(
    process.argv[2] || resolve(root, "../frontend/package-lock.json"),
    "utf8",
  ),
);
const target = JSON.parse(
  readFileSync(resolve(root, "frontend/package.json"), "utf8"),
);
const packages = {
  "": {
    name: target.name,
    version: target.version,
    dependencies: target.dependencies,
    devDependencies: target.devDependencies,
  },
};
function locate(parent, name) {
  let base = parent;
  while (true) {
    const key = (base ? base + "/" : "") + "node_modules/" + name;
    if (source.packages[key]) return key;
    if (!base) return null;
    base = posix.dirname(base);
    if (base === ".") base = "";
  }
}
function include(parent, name, optional = false) {
  const key = locate(parent, name);
  if (!key) {
    if (optional) return;
    throw new Error("Missing locked dependency: " + name);
  }
  if (packages[key]) return;
  const entry = source.packages[key];
  if (entry.link || key.includes(".."))
    throw new Error("External dependency link: " + key);
  packages[key] = entry;
  for (const dep of Object.keys(entry.dependencies || {})) include(key, dep);
  for (const dep of Object.keys(entry.optionalDependencies || {}))
    include(key, dep, true);
  for (const dep of Object.keys(entry.peerDependencies || {})) {
    if (!entry.peerDependenciesMeta?.[dep]?.optional) include(key, dep);
  }
}
for (const name of Object.keys({
  ...target.dependencies,
  ...target.devDependencies,
}))
  include("", name);
writeFileSync(
  resolve(root, "frontend/package-lock.json"),
  JSON.stringify(
    {
      name: target.name,
      version: target.version,
      lockfileVersion: 3,
      requires: true,
      packages,
    },
    null,
    2,
  ) + "\n",
);
console.log(
  "Locked " +
    (Object.keys(packages).length - 1) +
    " existing packages without downloads.",
);
