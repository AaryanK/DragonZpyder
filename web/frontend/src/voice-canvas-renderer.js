// Original uploaded DragonZpyder canvas artwork. React owns the controls and session;
// only the fluid visual rendering is imperative, for pixel-level preview fidelity.
// This renderer never opens a microphone, triggers an agent call or plays audio.
export function createVoiceOrbRenderer(canvas) {
  const ctx=canvas.getContext("2d",{alpha:false});
  if(!ctx)return{setActive(){},setInputStream(){},setOutputStream(){},setStatus(){},destroy(){}};
  const reduce=window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let W=0,H=0,DPR=1,cx=0,cy=0,radius=170,playing=false,demo=false;
  let analyser=null,data=null,outputAnalyser=null,outputData=null,outputLevel=0;
  let volume=0,smooth=0,bass=0,treble=0,frame=0,frameId=0,destroyed=false,active=false;
  let audioContext=null,inputSource=null,outputSource=null;
  const resize=()=>{
    if(destroyed)return;
    const rect=canvas.getBoundingClientRect();
    W=Math.max(1,rect.width);H=Math.max(1,rect.height);
    DPR=Math.min(window.devicePixelRatio||1,2);
    canvas.width=Math.round(W*DPR);canvas.height=Math.round(H*DPR);
    ctx.setTransform(DPR,0,0,DPR,0,0);
    cx=W/2;cy=H<650?H*.435:H*.448;
    radius=Math.min(W*.28,H*.248,226);
    // Preserve the source preview's 70%-width orb on phones. Desktop-site
    // browser mode may report 980 CSS px in a narrow physical phone.
    if(W<680){cy=H*.425;radius=Math.min(W*.35,H*.204,155)}
    else if(H>W*1.16){
      cy=H*.425;radius=Math.min(W*.35,H*.204);
    }
    canvas.dataset.orbRadius=radius.toFixed(2);
    canvas.dataset.orbCenterY=cy.toFixed(2);
    if(reduce||!active)draw(0);
  };
  const observer=new ResizeObserver(resize);observer.observe(canvas);
  function ensureContext(){
    if(!audioContext)audioContext=new (window.AudioContext||window.webkitAudioContext)();
    if(audioContext.state==="suspended")audioContext.resume().catch(()=>{});
    return audioContext;
  }
  function attach(stream,kind){
    if(!stream?.getAudioTracks?.().length)return;
    try{
      const ac=ensureContext(),source=ac.createMediaStreamSource(stream),meter=ac.createAnalyser();
      meter.fftSize=kind==="input"?2048:1024;meter.smoothingTimeConstant=.82;
      source.connect(meter); // Meter only. The companion audio element plays remote audio.
      const silentSink=ac.createGain();silentSink.gain.value=0;meter.connect(silentSink);silentSink.connect(ac.destination);
      if(kind==="input"){inputSource?.disconnect();inputSource=source;analyser=meter;data=new Uint8Array(meter.frequencyBinCount);playing=true}
      else{outputSource?.disconnect();outputSource=source;outputAnalyser=meter;outputData=new Uint8Array(meter.frequencyBinCount)}
    }catch(err){console.warn("Voice meter unavailable",err)}
  }
const rand=(a,b)=>a+Math.random()*(b-a);const stars=Array.from({length:145},()=>({x:Math.random(),y:Math.random(),z:rand(.2,1),phase:rand(0,6.283)}));const motes=Array.from({length:230},()=>({a:rand(0,6.283),d:rand(.8,2.05),v:rand(.00011,.00051)*(Math.random()<.5?-1:1),size:rand(.5,2),phase:rand(0,6.28)}));
function line(points,color,width=1){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();for(let i=0;i<points.length;i++){const p=points[i];if(i===0)ctx.moveTo(p[0],p[1]);else ctx.lineTo(p[0],p[1])}ctx.stroke()}
function draw(t){frame++;const time=reduce?2:t*.001;ctx.fillStyle='#08090d';ctx.fillRect(0,0,W,H);
let raw=0;if(playing&&analyser){analyser.getByteFrequencyData(data);let sum=0,low=0,high=0;for(let i=2;i<Math.min(340,data.length);i++){sum+=data[i];if(i<45)low+=data[i];if(i>140)high+=data[i]}raw=Math.min(1,sum/(338*100));bass=low/(43*130);treble=high/(199*125)}else if(false){raw=0}else{bass*=.94;treble*=.94}if(outputAnalyser&&outputData){outputAnalyser.getByteFrequencyData(outputData);let out=0;for(let i=0;i<outputData.length;i++)out+=outputData[i];raw=Math.max(raw,Math.min(1,out/(outputData.length*95)))}raw=Math.max(raw,outputLevel||0);volume=raw;smooth+=(raw-smooth)*.09;const energy=Math.min(1.6,smooth);const p=1+energy*.12;
// Expose numerical diagnostics for regression tests; they are not artificial inputs.
canvas.dataset.audioEnergy=energy.toFixed(3);
canvas.dataset.renderRadius=(radius*p).toFixed(2);
// Ambient gradients and horizon
let glow=ctx.createRadialGradient(cx,cy,0,cx,cy,Math.max(W,H)*.75);glow.addColorStop(0,'rgba(14,53,68,.62)');glow.addColorStop(.34,'rgba(9,27,44,.27)');glow.addColorStop(1,'rgba(5,8,17,0)');ctx.fillStyle=glow;ctx.fillRect(0,0,W,H);
let bottom=ctx.createRadialGradient(cx,H*.9,0,cx,H*.9,W*.8);bottom.addColorStop(0,'rgba(15,48,66,.18)');bottom.addColorStop(1,'transparent');ctx.fillStyle=bottom;ctx.fillRect(0,0,W,H);
for(const s of stars){let a=(.13+.24*Math.sin(time*.45+s.phase)**2)*s.z;ctx.fillStyle=`rgba(115,199,216,${a})`;ctx.beginPath();ctx.arc(s.x*W,s.y*H,s.z*.92,0,Math.PI*2);ctx.fill()}
// Faint technical rings
ctx.save();ctx.translate(cx,cy);for(let j=0;j<4;j++){const rr=radius*(1.48+j*.22);ctx.strokeStyle=`rgba(83,194,220,${.045-j*.007+energy*.025})`;ctx.lineWidth=.6;ctx.beginPath();ctx.ellipse(0,0,rr,rr*(.66+j*.04),-.21,0,Math.PI*2);ctx.stroke()}ctx.restore();
// Atmospheric glow
const R=radius*p;ctx.save();ctx.globalCompositeOperation='screen';const halo=ctx.createRadialGradient(cx,cy,R*.47,cx,cy,R*2.25);halo.addColorStop(0,`rgba(250,142,100,${.10+energy*.09})`);halo.addColorStop(.42,`rgba(98,84,183,${.065+energy*.07})`);halo.addColorStop(1,'rgba(10,40,80,0)');ctx.fillStyle=halo;ctx.beginPath();ctx.arc(cx,cy,R*2.25,0,Math.PI*2);ctx.fill();ctx.restore();
// Fluid orb body
ctx.save();ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.clip();let sphere=ctx.createRadialGradient(cx-R*.31,cy-R*.39,R*.04,cx+R*.2,cy+R*.18,R*1.48);sphere.addColorStop(0,'#c27d6c');sphere.addColorStop(.21,'#92516b');sphere.addColorStop(.46,'#402d59');sphere.addColorStop(.73,'#151d3a');sphere.addColorStop(1,'#0b1427');ctx.fillStyle=sphere;ctx.fillRect(cx-R,cy-R,R*2,R*2);
// Internal flowing plasma layers, multi-sine ribbons
ctx.globalCompositeOperation='screen';for(let k=0;k<13;k++){let pts=[];const kk=k/12;for(let i=0;i<=180;i++){const x=-R*1.34+i/180*R*2.68;const v=x/R;const y=R*((kk-.5)*1.32 + .15*Math.sin(v*3.4+time*(.17+kk*.22)+kk*7)+.092*Math.sin(v*8.1-time*.38+kk*3.4)+.04*Math.sin(v*13+time*.67+kk*9));pts.push([cx+x,cy+y]);}const alpha=.03+.065*(1-Math.abs(kk-.5)*1.8)+energy*.035;line(pts,`rgba(${Math.round(197+kk*38)},${Math.round(107+kk*55)},${Math.round(150+kk*44)},${alpha})`,R*(.027+kk*.012))}
for(let j=0;j<5;j++){const phase=time*(.24+j*.06)+j*1.85;const gg=ctx.createRadialGradient(cx+Math.sin(phase)*R*.5,cy+Math.cos(phase*.82)*R*.42,0,cx+Math.sin(phase)*R*.5,cy+Math.cos(phase*.82)*R*.42,R*(.55+j*.045));gg.addColorStop(0,`rgba(${j%2?248:142},${j%2?149:93},${j%2?116:207},${.12+energy*.08})`);gg.addColorStop(1,'transparent');ctx.fillStyle=gg;ctx.fillRect(cx-R,cy-R,R*2,R*2)}
// Delicate flow bands following curved latitudes
for(let j=0;j<50;j++){const lat=(j/49-.5)*2.1,points=[];for(let i=0;i<110;i++){const q=i/109,xx=(q-.5)*R*2.85, wav=.1*Math.sin(xx/R*4.1+time*.33+j*.27)+.035*Math.cos(xx/R*12-time*.5+j*.17);const yy=(lat*.66+wav)*R;points.push([cx+xx,cy+yy])}line(points,`rgba(249,181,203,${.025+.034*Math.sin(j*.17+time*.22)**2})`,.6)}
const shade=ctx.createRadialGradient(cx-R*.31,cy-R*.36,R*.02,cx,cy,R*1.12);shade.addColorStop(0,'rgba(255,213,170,.24)');shade.addColorStop(.45,'rgba(8,54,94,0)');shade.addColorStop(.76,'rgba(0,10,30,.16)');shade.addColorStop(1,'rgba(0,2,14,.8)');ctx.fillStyle=shade;ctx.fillRect(cx-R,cy-R,R*2,R*2);ctx.restore();
// Fresnel rim and highlights
ctx.save();ctx.globalCompositeOperation='screen';let rim=ctx.createLinearGradient(cx-R,cy-R,cx+R,cy+R);rim.addColorStop(0,'rgba(255,224,184,.84)');rim.addColorStop(.22,'rgba(252,166,123,.52)');rim.addColorStop(.52,'rgba(49,137,220,.15)');rim.addColorStop(.81,'rgba(44,145,205,.38)');rim.addColorStop(1,'rgba(255,156,132,.72)');ctx.strokeStyle=rim;ctx.lineWidth=1.5+energy*1.7;ctx.shadowColor='#f5a475';ctx.shadowBlur=24+energy*18;ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.stroke();ctx.shadowBlur=0;ctx.beginPath();ctx.arc(cx,cy,R*.985,-2.67,-1.08);ctx.strokeStyle='rgba(255,222,198,.3)';ctx.lineWidth=2.3;ctx.stroke();ctx.restore();
// Orbiting filaments with energy-linked distortion
ctx.save();ctx.translate(cx,cy);for(let k=0;k<3;k++){const points=[],dir=k%2?1:-1;for(let i=0;i<=360;i++){const a=i/360*Math.PI*2;const dist=R*(1.13+k*.14)+R*(.019+.045*energy)*Math.sin(a*10-time*(2.4+k)+k*2);const x=dist*Math.cos(a),y=dist*Math.sin(a)*(.71+k*.065);const rot=-.35+k*.43+time*(k===1?.032:-.023);points.push([x*Math.cos(rot)-y*Math.sin(rot),x*Math.sin(rot)+y*Math.cos(rot)])}line(points,`rgba(${k?77:104},${k?171:230},255,${.105+energy*.09})`,k===1?1.2:.75)}ctx.restore();
// Responsive spectral ripple rings
for(let k=0;k<3;k++){let progress=((time*(.24+energy*.25)+k/3)%1);const rr=R*(1.04+progress*.68);ctx.beginPath();ctx.ellipse(cx,cy,rr,rr*.86,-.23,0,Math.PI*2);ctx.strokeStyle=`rgba(81,218,239,${(.10+energy*.12)*(1-progress)})`;ctx.lineWidth=.7+energy*.8;ctx.stroke()}
// Tiny rotating motes
ctx.save();ctx.globalCompositeOperation='screen';for(const m of motes){const a=m.a+time*m.v*550,dist=R*(m.d+.03*Math.sin(time*.8+m.phase));const x=cx+Math.cos(a)*dist,y=cy+Math.sin(a)*dist*.80;const alpha=(.13+.26*Math.sin(time+m.phase)**2)*(1-Math.max(0,m.d-1.5)*.5);ctx.fillStyle=`rgba(255,179,150,${alpha})`;ctx.beginPath();ctx.arc(x,y,m.size*(.7+energy*.55),0,Math.PI*2);ctx.fill()}ctx.restore();
// Waveform at bottom of orb, subtle when idle
const waveY=cy+R*1.7,range=Math.min(W*.36,350),pointsA=[],pointsB=[];for(let i=0;i<=150;i++){const x=(i/150*2-1),env=Math.pow(Math.max(0,1-Math.abs(x)),1.5),sig=Math.sin(x*34+time*2)*.48+Math.sin(x*71-time*3.5)*.30+Math.sin(x*113+time*1.5)*.22;const amp=3+energy*47;pointsA.push([cx+x*range,waveY+sig*env*amp]);pointsB.push([cx+x*range,waveY+sig*env*amp*.55])}ctx.save();ctx.shadowBlur=10;ctx.shadowColor='#f4a67d';line(pointsA,`rgba(104,230,243,${.16+energy*.56})`,1.3);ctx.shadowBlur=0;line(pointsB,`rgba(94,181,230,${.09+energy*.26})`,.75);ctx.restore();
if(!reduce&&!destroyed&&active)frameId=requestAnimationFrame(draw)}

  resize();draw(0);
  return {
    setActive(next){active=Boolean(next);cancelAnimationFrame(frameId);if(active)resize();if(active&&!reduce)frameId=requestAnimationFrame(draw);else draw(0)},
    setInputStream(stream){if(stream)attach(stream,"input");else{inputSource?.disconnect();inputSource=null;analyser=null;data=null;playing=false}},
    setOutputStream(stream){if(stream)attach(stream,"output");else{outputSource?.disconnect();outputSource=null;outputAnalyser=null;outputData=null}},
    setStatus(status){if(status==="ended"||status==="error")outputLevel=0},
    destroy(){destroyed=true;cancelAnimationFrame(frameId);observer.disconnect();inputSource?.disconnect();outputSource?.disconnect();audioContext?.close().catch(()=>{});audioContext=null},
  };
}
