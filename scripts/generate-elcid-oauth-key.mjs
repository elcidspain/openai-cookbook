import { randomBytes } from "node:crypto";
import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const root = process.cwd();
const output = resolve(root, "api/_elcid-oauth-key.js");
const publicDir = resolve(root, "public");
const key = randomBytes(48).toString("base64url");

await mkdir(dirname(output), { recursive: true });
await writeFile(
  output,
  `// Generated during Vercel build. Never commit this file.\nexport const ELCID_OAUTH_BUILD_KEY = ${JSON.stringify(key)};\n`,
  { encoding: "utf8", mode: 0o600 },
);

await rm(publicDir, { recursive: true, force: true });
await mkdir(publicDir, { recursive: true });
await cp(resolve(root, "elcid-site"), resolve(publicDir, "elcid-site"), { recursive: true });
await cp(resolve(root, "staff"), resolve(publicDir, "staff"), { recursive: true });

console.log("Generated EL CID OAuth key and preserved static output in public/.");
