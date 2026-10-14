import test from "node:test";
import assert from "node:assert/strict";
import { formatImageWait } from "../image-progress.mjs";

test("image wait display reports elapsed time, not fake rendering percentage", () => {
  assert.equal(formatImageWait(0), "Waiting for provider · 0:00 elapsed");
  assert.equal(formatImageWait(999), "Waiting for provider · 0:00 elapsed");
  assert.equal(formatImageWait(1250), "Waiting for provider · 0:01 elapsed");
  assert.equal(formatImageWait(61250), "Waiting for provider · 1:01 elapsed");
  assert.equal(formatImageWait(3599000), "Waiting for provider · 59:59 elapsed");
  assert.equal(formatImageWait(-120), "Waiting for provider · 0:00 elapsed");
  assert.equal(formatImageWait(Infinity), "Waiting for provider · 0:00 elapsed");
});
