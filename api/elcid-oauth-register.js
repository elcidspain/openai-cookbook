import { cors, registerClient } from "../elcid-server/oauth-core.js";

export default function handler(req, res) {
  cors(res, "POST, OPTIONS");
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST, OPTIONS");
    return res.status(405).end();
  }
  try {
    const input = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
    return res.status(201).json(registerClient(input));
  } catch (error) {
    return res.status(400).json({
      error: "invalid_client_metadata",
      error_description: error instanceof Error ? error.message : "Invalid client metadata",
    });
  }
}
