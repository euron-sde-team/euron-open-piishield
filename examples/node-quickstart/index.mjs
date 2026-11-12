// The Node.js quickstart: scan, mask and tokenize one string, then protect and restore
// a prompt through the AI gateway.
//
//   export PIISHIELD_API_URL=http://localhost:8000
//   export PIISHIELD_API_KEY=YOUR_API_KEY
//   export PIISHIELD_PROJECT_ID=YOUR_PROJECT_ID
//   pnpm start

import { APIError, PIIShield } from "@euron/piishield";

const shield = new PIIShield({
  apiUrl: process.env.PIISHIELD_API_URL ?? "http://localhost:8000",
  apiKey: process.env.PIISHIELD_API_KEY,
  projectId: process.env.PIISHIELD_PROJECT_ID,
});

const text = "Customer: Rahul Sharma\nEmail: rahul@example.com\nPhone: 9876543210";
console.log("Input:");
console.log(text);
console.log();

try {
  const scanned = await shield.scan(text);
  console.log(`Found ${scanned.findings.length} finding(s):`);
  for (const finding of scanned.findings) {
    console.log(`  ${finding.category.padEnd(12)} [${finding.start}:${finding.end}] confidence=${finding.confidence.toFixed(2)}`);
  }
  console.log();

  const masked = await shield.mask(text);
  console.log("Protected (method=full_mask, the default):");
  console.log(masked.protectedText);
  console.log();

  const tokenized = await shield.tokenize(text, { scopeId: "node-quickstart-demo" });
  console.log("Protected (method=tokenize, scopeId=node-quickstart-demo):");
  console.log(tokenized.protectedText);
  console.log();

  // AI gateway: protect a prompt, pretend to call an external model, restore the response.
  // ABCPE1234F is a structurally valid PAN (4th letter P = person); the real,
  // checksum-validated recognizer only finds a valid one.
  const protected_ = await shield.protect("My PAN is ABCPE1234F. Explain my tax record.");
  console.log(`AI gateway protected text (safe for a model): ${protected_.protectedText}`);
  const modelResponse = protected_.protectedText.replace("Explain", "Explained");
  const restored = await shield.restore(protected_.scopeId, modelResponse);
  console.log(`AI gateway restored text (for this app only): ${restored.restoredText}`);

  process.exit(scanned.findings.length > 0 ? 0 : 1);
} catch (error) {
  if (error instanceof APIError) {
    console.error(`piishield call failed: ${error.message} (${error.code})`);
  } else {
    console.error(error);
  }
  process.exit(1);
}
