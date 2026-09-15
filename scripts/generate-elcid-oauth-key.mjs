import { randomBytes } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const output = resolve(process.cwd(), "api/_elcid-oauth-key.js");
const key = randomBytes(48).toString("base64url");

await mkdir(dirname(output), { recursive: true });
await writeFile(
  output,
  `// Generated during Vercel build. Never commit this file.\nexport const ELCID_OAUTH_BUILD_KEY = ${JSON.stringify(key)};\n`,
  { encoding: "utf8", mode: 0o600 },
);

console.log("Generated per-deployment EL CID agent OAuth signing key.");
