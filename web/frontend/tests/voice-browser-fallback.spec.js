import { test, expect } from "@playwright/test";

async function prepare(page, status = 503) {
  await page.addInitScript(() => {
    window.__voiceFixture = { starts:0, aborts:0, closed:0 };
    class Recognition {
      start() {
        window.__voiceFixture.starts++;
        window.__recognition = this;
        queueMicrotask(() => this.onstart?.());
      }
      abort() {
        window.__voiceFixture.aborts++;
        queueMicrotask(() => this.onend?.());
      }
    }
    Object.defineProperty(window, "SpeechRecognition", { configurable:true, value:Recognition });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable:true, value:{ getUserMedia:async () => new MediaStream() }
    });
    class Peer {
      addTrack(){}
      createDataChannel(){return { close(){}, readyState:"closed" }}
      async createOffer(){return {type:"offer",sdp:"test-offer"}}
      async setLocalDescription(offer){this.localDescription=offer}
      addEventListener(){}
      close(){window.__voiceFixture.closed++}
    }
    Object.defineProperty(window,"RTCPeerConnection",{configurable:true,value:Peer});
  });
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let body = {};
    if(path === "/api/auth/sessions") body=[{id:"fixture",current:true,scope:"personal",device:"test"}];
    if(path === "/api/personal-agent/conversations" || path.endsWith("/approvals")) body=[];
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(body)});
  });
  await page.route("**/mesh/**", route => route.fulfill({status:200,contentType:"application/json",body:'{"models":[],"imageEnabled":false,"videoEnabled":false}'}));
  await page.route("**/companion/realtime", route => route.fulfill({status,contentType:"application/json",body:JSON.stringify({detail:{message:status===503?"Live voice is not configured":"Access denied"}})}));
  await page.goto("/app");
  await expect(page.locator("#app-shell")).toBeVisible();
}
test("provider unavailable falls back to browser captions, with pause and cleanup", async ({page}) => {
  await page.setViewportSize({width:390,height:750});
  await prepare(page);
  const submitted=[];
  page.on("request", request => { if(request.method()==="POST" && /personal-agent/.test(request.url())) submitted.push(request.url()); });
  await page.locator("#companion-open").click();
  const panel=page.getByRole("dialog",{name:"Live companion"});
  await expect(panel.getByText("TRANSCRIPTION",{exact:true})).toBeVisible();
  await expect(panel.locator("#companion-status")).toContainText("Listening");
  await expect(panel.getByRole("button",{name:"Mute speaker"})).toBeDisabled();
  await expect.poll(() => page.evaluate(() => window.__voiceFixture.closed)).toBeGreaterThan(0);
  await page.evaluate(() => window.__recognition.onresult({resultIndex:0,results:[Object.assign([{transcript:"Testing Dragon"}],{isFinal:false})]}));
  await expect(panel.getByLabel("Latest transcription")).toHaveText("Testing Dragon");
  await page.evaluate(() => window.__recognition.onresult({resultIndex:0,results:[Object.assign([{transcript:"Testing DragonZpyder voice"}],{isFinal:true})]}));
  await expect(panel.getByLabel("Latest transcription")).toHaveText("Testing DragonZpyder voice");
  await expect(panel.getByLabel("Latest transcription")).toHaveAttribute("data-interim","false");
  await panel.getByRole("button",{name:"Show transcript"}).click();
  await expect(panel.locator("#companion-transcript p")).toHaveCount(1);
  await panel.getByRole("button",{name:"Hide transcript"}).click();
  await panel.getByRole("button",{name:"Mute microphone"}).click();
  await expect(panel.getByRole("button",{name:"Unmute microphone"})).toBeEnabled();
  await expect(panel.locator("#companion-status")).toContainText("resume");
  await panel.getByRole("button",{name:"Unmute microphone"}).click();
  await expect.poll(() => page.evaluate(() => window.__voiceFixture.starts)).toBe(2);
  await expect(panel.getByLabel("Latest transcription")).toHaveText("Testing DragonZpyder voice");
  await panel.getByRole("button",{name:"End conversation"}).click();
  await expect(panel).toBeHidden();
  await expect.poll(() => page.evaluate(() => window.__voiceFixture.aborts)).toBeGreaterThanOrEqual(2);
  expect(submitted).toEqual([]);
});
test("authorization errors do not start browser recognition automatically",async ({page})=>{
  await prepare(page,403);
  await page.locator("#companion-open").click();
  const panel=page.getByRole("dialog",{name:"Live companion"});
  await expect(panel.getByRole("alert")).toContainText("Access denied");
  expect(await page.evaluate(()=>window.__voiceFixture.starts)).toBe(0);
  await expect(panel.getByRole("button",{name:"Mute microphone"})).toBeDisabled();
  await panel.getByRole("button",{name:"Back to chat"}).click();
});
