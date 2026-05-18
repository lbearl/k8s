import PostalMime from "postal-mime";

export default {
  async email(message, env, ctx) {
    const subject = message.headers.get("subject") || "(no subject)";
    const from = message.headers.get("from") || "unknown";

    const rawEmail = new Response(message.raw);
    const rawBytes = await rawEmail.arrayBuffer();

    const parser = new PostalMime();
    const parsed = await parser.parse(rawBytes);

    let body = parsed.text || "";
    if (!body && parsed.html) {
      body = parsed.html
        .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
        .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
        .replace(/<[^>]+>/g, " ")
        .replace(/&nbsp;/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    }

    if (body.length > 3000) body = body.slice(0, 3000) + "\n...(truncated)";

    await fetch("https://hooks.bearl.me/webhook/email-to-planka", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from, subject, text: body }),
    });
  },
};
