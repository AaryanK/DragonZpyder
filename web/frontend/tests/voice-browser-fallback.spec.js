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

for (const viewport of [{width:390,height:750},{width:980,height:1830},{width:360,height:600}]) {
  test(`transcription is readable and usable in portrait ${viewport.width}x${viewport.height}`, async ({page})=>{
    await page.setViewportSize(viewport);
    await prepare(page);
    await page.locator("#companion-open").click();
    const panel=page.getByRole("dialog",{name:"Live companion"});
    await expect(panel.getByText("TRANSCRIPTION",{exact:true})).toBeVisible();
    await expect(panel.locator(".dz-voice-orb-footnote")).toBeHidden();
    await expect(panel.locator("canvas.dz-voice-original-canvas")).toBeVisible();
    await page.evaluate(() => window.__recognition.onresult({resultIndex:0,results:[Object.assign([{transcript:"This is a live transcription test."}],{isFinal:true})]}));
    await expect(panel.getByLabel("Latest transcription")).toHaveText("This is a live transcription test.");
    const metrics=await page.evaluate(()=>{
      const rect=selector=>document.querySelector(selector).getBoundingClientRect();
      const scale=innerWidth/390;
      const canvas=document.querySelector("canvas.dz-voice-original-canvas");
      const canvasRect=canvas.getBoundingClientRect();
      const orbRadius=Number(canvas.dataset.orbRadius);
      const orbBottom=canvasRect.top+Number(canvas.dataset.orbCenterY)+orbRadius;
      const mic=rect("#companion-mute"),speaker=rect(".dz-voice-orb-controls button"),area=rect(".dz-voice-orb-space"),caption=rect(".dz-voice-live-caption"),text=rect(".dz-voice-orb-conversation"),controls=rect(".dz-voice-orb-controls"),end=rect("#companion-end"),header=rect(".dz-voice-orb-head");
      return {scale, mic:mic.width,speaker:speaker.width,orb:orbRadius*2,orbBottom,areaBottom:area.bottom,textTop:text.top,captionBottom:caption.bottom,controlsTop:controls.top,controlsBottom:controls.bottom,endTop:end.top,endBottom:end.bottom,headerRight:header.right,width:innerWidth,height:innerHeight,captionFont:parseFloat(getComputedStyle(document.querySelector(".dz-voice-live-caption")).fontSize)};
    });
    expect(metrics.mic/metrics.scale).toBeGreaterThanOrEqual(64);
    expect(metrics.speaker/metrics.scale).toBeGreaterThanOrEqual(48);
    expect(metrics.captionFont/metrics.scale).toBeGreaterThanOrEqual(18);
    expect(metrics.orb/metrics.width).toBeGreaterThanOrEqual(.5);
    // The source artwork deliberately reaches the title baseline by ~20px.
    // Do not force the fluid orb entirely into the invisible spacing element.
    expect(metrics.orbBottom-metrics.textTop).toBeLessThanOrEqual(39*metrics.scale);
    expect(metrics.areaBottom).toBeLessThan(metrics.textTop);
    expect(metrics.captionBottom).toBeLessThan(metrics.controlsTop);
    expect(metrics.controlsBottom).toBeLessThan(metrics.endTop);
    expect(metrics.endBottom).toBeLessThanOrEqual(metrics.height+1);
    expect(metrics.headerRight).toBeLessThanOrEqual(metrics.width+1);
    await panel.getByRole("button",{name:"End conversation"}).click();
  });
}
