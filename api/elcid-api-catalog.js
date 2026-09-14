const catalog = {
  linkset: [
    {
      anchor: "https://www.elcidspain.com/mcp",
      "service-desc": [
        { href: "https://www.elcidspain.com/.well-known/mcp/server-card.json", type: "application/json" }
      ],
      "service-doc": [
        { href: "https://www.elcidspain.com/llms.txt", type: "text/plain" }
      ],
      "service-meta": [
        { href: "https://www.elcidspain.com/.well-known/agent-skills/index.json", type: "application/json" }
      ]
    },
    {
      anchor: "https://www.elcidspain.com/a2a",
      "service-desc": [
        { href: "https://www.elcidspain.com/.well-known/agent-card.json", type: "application/json" }
      ],
      "service-doc": [
        { href: "https://www.elcidspain.com/llms.txt", type: "text/plain" }
      ]
    }
  ]
};

export default function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Cache-Control", "public, max-age=300");
  res.setHeader("Content-Type", "application/linkset+json; profile=\"https://www.rfc-editor.org/info/rfc9727\"");
  res.setHeader("Link", '</.well-known/api-catalog>; rel="api-catalog"');
  if (req.method === "HEAD") return res.status(200).end();
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET, HEAD");
    return res.status(405).end();
  }
  return res.status(200).json(catalog);
}
