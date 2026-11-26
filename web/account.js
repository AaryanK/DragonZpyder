const $ = (id) => document.getElementById(id);
const panels = ["login","signup","verify","forgot","reset","profile","migration","migration-recovery"];
let mode = "login", bootstrap = null, challenge = null, processing = false, initializedGoogle = false;
let nativeMode = false, googleRenderedMode = null, nativeGoogleState = null;
let migrationEnabled = false, recoveryEnabled = false, recoveryEmail = null;
let activeRecoveryEnabled=false;
const messageBox = $("account-message");
function report(message,isError=false){messageBox.textContent=String(message||"");messageBox.classList.toggle("error",isError);messageBox.hidden=!message;}
function show(next){if(!panels.includes(next))next="login";if(next==="migration"&&!migrationEnabled)next="login";if(next==="migration-recovery"&&!recoveryEnabled)next="login";if(nativeMode&&!["login","signup","profile","migration","migration-recovery",...(activeRecoveryEnabled?["forgot","reset"]:[])].includes(next))next="login";mode=next;report("");panels.forEach(name=>{$(name+"-panel").hidden=name!==next});$("mode-tabs").hidden=!["login","signup"].includes(next);document.querySelectorAll("[data-mode]").forEach(el=>el.classList.toggle("selected",el.dataset.mode===next));if(next==="login"||(nativeMode&&next==="signup")||next==="migration")loadGoogle().catch(()=>{});}
function cookie(name){const part=document.cookie.split(";").map(v=>v.trim()).find(v=>v.startsWith(name+"="));return part?decodeURIComponent(part.slice(name.length+1)):"";}
function csrf(){return nativeMode?cookie("__Host-dz_csrf"):(cookie("__Host-operly_csrf")||cookie("operly_csrf")||bootstrap?.csrf_token||"");}
async function loadBootstrap(){
 if(nativeMode){bootstrap={};return bootstrap;}
 bootstrap=await request("/api/auth/bootstrap",{method:"GET",unauth:true});
 const central=$("dragonzpyder-central-signin");
 if(central)central.hidden=false;
 return bootstrap;
}
async function request(path,{method="GET",body,unauth=false}={}){
 const headers={accept:"application/json"};
 if(body!==undefined)headers["content-type"]="application/json";
 if(method!=="GET"&&method!=="HEAD"){
  if(nativeMode)headers["X-DZ-CSRF"]=csrf();
  else headers["X-CSRF-Token"]=csrf();
 }
 const response=await fetch(path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),credentials:"same-origin",redirect:"error",cache:"no-store"});
 const payload=await response.json().catch(()=>({}));
 if(!response.ok){const d=payload.detail;const error=new Error(typeof d==="string"?d:d?.message||"Request failed ("+response.status+")");error.status=response.status;error.code=d?.code;throw error;}
 return payload;
}
async function submitAction(form,action){
 if(processing)return;processing=true;
 const button=form.querySelector("button[type='submit']");if(button)button.disabled=true;
 report("");
 try{await action()}catch(error){report(error?.message||"Something went wrong. Please try again.",true)}
 finally{processing=false;if(button)button.disabled=false}
}
function adminReturnRequested(){return new URLSearchParams(window.location.search).get("next")==="/admin";}
function authenticated(){window.location.replace(adminReturnRequested()?"/admin":"/app");}
async function ensurePersonal(){
 if(nativeMode){await request("/dz/identity/v1/me");return;}
 let response=await request("/api/auth/sessions");
 const current=Array.isArray(response)?response.find(item=>item?.current):null;
 if(!current)throw Error("Could not establish your session.");
 if(current.scope!=="personal"){await request("/api/auth/personal-scope",{method:"POST",body:{}});response=await request("/api/auth/sessions");if(!Array.isArray(response)||!response.some(item=>item?.current&&item.scope==="personal"))throw Error("Personal session unavailable.")}
}
async function afterSignIn(){await ensurePersonal();authenticated();}
function reportProof(result){
 if(result?.status!=="awaiting_review"||!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(result.proof_reference||""))throw Error("Verification response unavailable.");
 report("Verification recorded. No account has been activated. Review reference: "+result.proof_reference);
}
async function googleCredential(credential,expectedMode){
 if(mode!==expectedMode)return;
 if(!credential||processing)return;
 processing=true;report("");
 try{
  if(mode==="migration"){
   if(!migrationEnabled||!nativeGoogleState?.state)throw Error("Verification challenge expired. Reload and retry.");
   const result=await request("/dz/identity/v1/import-proof/google/complete",{method:"POST",body:{state:nativeGoogleState.state,credential}});
   nativeGoogleState=null;reportProof(result);return;
  }
  if(nativeMode){
   if(!nativeGoogleState?.state)throw Error("Google sign-in challenge expired. Retry.");
   const action=mode==="signup"?"signup":"complete";
   await request("/dz/identity/v1/provider/google/"+action,{method:"POST",body:{state:nativeGoogleState.state,credential}});
   nativeGoogleState=null;
  }else await request("/api/auth/google",{method:"POST",body:{credential}});
  await afterSignIn();
 }catch(e){report(e.message||"Google sign-in failed.",true)}finally{processing=false}
}
async function loadGoogle(){
 if(mode==="migration"){
  if(!migrationEnabled||googleRenderedMode===mode)return;
  const g=await request("/dz/identity/v1/import-proof/google/start",{method:"POST"});
  if(mode!=="migration")return;
  nativeGoogleState=g;
  if(g.client_id&&g.nonce)return renderGoogle(g.client_id,g.nonce,"google-provider-migration");
  return;
 }
 if(mode!=="login"&&!(nativeMode&&mode==="signup"))return;
 if(nativeMode){
  if(googleRenderedMode===mode)return;
  const g=await request("/dz/identity/v1/provider/google/start",{method:"POST"});
  nativeGoogleState=g;
  if(!g.client_id||!g.nonce)return;
  return renderGoogle(g.client_id,g.nonce,mode==="signup"?"google-provider-signup":"google-provider");
 }
 if(initializedGoogle)return;
 const g=bootstrap||await loadBootstrap();
 if(!g.google_client_id||!g.google_nonce)return;
 return renderGoogle(g.google_client_id,g.google_nonce,"google-provider");
}
function renderGoogle(clientId,nonce,hostId){
 const expectedMode=mode;
 const render=()=>{if(mode!==expectedMode||!window.google?.accounts?.id)return;
  const host=$(hostId);host.hidden=false;
  window.google.accounts.id.initialize({client_id:clientId,nonce,callback:result=>googleCredential(String(result?.credential||""),expectedMode),auto_select:false,cancel_on_tap_outside:true});
  host.replaceChildren();
  window.google.accounts.id.renderButton(host,{theme:"outline",size:"large",text:"continue_with",shape:"rectangular",width:Math.min(400,Math.max(200,Math.floor(host.clientWidth||300)))});
  initializedGoogle=true;googleRenderedMode=mode;
 };
 if(window.google?.accounts?.id){render();return;}
 const script=document.createElement("script");script.src="https://accounts.google.com/gsi/client";script.async=true;script.defer=true;script.onload=render;script.onerror=()=>report("Google sign-in could not load; use email to continue.",true);document.head.append(script);
}
document.querySelectorAll("[data-mode]").forEach(el=>el.addEventListener("click",()=>show(el.dataset.mode)));
$("migration-recovery-start").addEventListener("submit",e=>{e.preventDefault();if(mode!=="migration-recovery"||!recoveryEnabled)return;submitAction(e.currentTarget,async()=>{
 const email=$("migration-recovery-email").value.trim();
 const result=await request("/dz/identity/v1/import-proof/recovery/start",{method:"POST",body:{email}});
 if(result.status!=="if_eligible_sent")throw Error("Recovery is unavailable.");
 recoveryEmail=email;
 $("migration-recovery-complete").hidden=false;
 report("If this account is eligible, a one-time code has been sent. Check your email.");
})});
$("migration-recovery-complete").addEventListener("submit",e=>{e.preventDefault();if(mode!=="migration-recovery"||!recoveryEnabled||!recoveryEmail)return;submitAction(e.currentTarget,async()=>{
 const p=$("migration-recovery-password"), c=$("migration-recovery-confirm"), code=$("migration-recovery-code");
 if(p.value!==c.value)throw Error("Passwords do not match.");
 const body={email:recoveryEmail,code:code.value.trim(),password:p.value};
 p.value="";c.value="";code.value="";
 const result=await request("/dz/identity/v1/import-proof/recovery/complete",{method:"POST",body});
 reportProof(result);$("migration-recovery-complete").hidden=true;recoveryEmail=null;
})});
$("migration-form").addEventListener("submit",e=>{e.preventDefault();if(mode!=="migration"||!migrationEnabled)return;submitAction(e.currentTarget,async()=>{
 const passwordInput=$("migration-password");
 const password=passwordInput.value;passwordInput.value="";
 const result=await request("/dz/identity/v1/import-proof/password",{method:"POST",body:{email:$("migration-email").value.trim(),password}});
 reportProof(result);
})});
$("login-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 await loadBootstrap();
 try{await request(nativeMode?"/dz/identity/v1/password/login":"/api/auth/login",{method:"POST",body:{email:$("login-email").value.trim(),password:$("login-password").value}});await afterSignIn()}
 catch(err){if(err.code==="EMAIL_NOT_VERIFIED"){challenge={email:$("login-email").value.trim()};$("verify-email").value=challenge.email;show("verify");report("Please verify your email to continue.");return;}throw err}
})});
$("signup-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 if(nativeMode)throw Error("Native account creation currently requires Google verification.");
 const password=$("signup-password").value;
 if(password!==$("signup-confirm").value)throw Error("Passwords do not match.");
 await loadBootstrap();
 const result=await request("/api/auth/signup",{method:"POST",body:{display_name:$("signup-name").value.trim(),email:$("signup-email").value.trim(),password}});
 challenge={id:result.challenge_id,email:result.email};$("verify-email").value=result.email;show("verify");report("Account created. Enter the code sent to your email.");
})});
$("verify-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 const body={email:$("verify-email").value.trim(),code:$("verify-code").value.trim()};if(challenge?.id)body.challenge_id=challenge.id;
 await request("/api/auth/verify-email",{method:"POST",body});await afterSignIn();
})});
$("resend").addEventListener("click",async()=>{try{await loadBootstrap();await request("/api/auth/resend-verification",{method:"POST",body:{email:$("verify-email").value.trim()}});report("If verification is pending, another code is on its way.");}catch(e){report(e.message,true)}});
$("forgot-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 await loadBootstrap();await request(nativeMode?"/dz/identity/v1/recovery/start":"/api/auth/forgot-password",{method:"POST",body:{email:$("forgot-email").value.trim()}});
 $("reset-email").value=$("forgot-email").value.trim();show("reset");report("If the account exists, password reset instructions were sent.");
})});
$("reset-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 await loadBootstrap();const password=$("reset-password").value;const code=$("reset-code").value.trim();$("reset-password").value="";$("reset-code").value="";await request(nativeMode?"/dz/identity/v1/recovery/complete":"/api/auth/reset-password",{method:"POST",body:{email:$("reset-email").value.trim(),code,password}});
 show("login");report("Password updated. Sign in with your new password.");
})});
$("profile-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 await request(nativeMode?"/dz/identity/v1/me":"/api/auth/me",{method:"PATCH",body:{display_name:$("profile-name").value.trim()}});report("Your account has been updated.");
})});
$("account-logout").addEventListener("click",async()=>{try{await request(nativeMode?"/dz/identity/v1/logout":"/api/auth/logout",{method:"POST",body:{}});window.location.replace(nativeMode?"/login":"/account")}catch(e){report(e.message,true)}});
async function profile(){
 const p=await request(nativeMode?"/dz/identity/v1/me":"/api/auth/me");$("profile-email").textContent=p.email||"";$("profile-name").value=p.display_name||"";
 const avatar=$("account-profile-avatar"), fallback=$("account-profile-fallback");
 avatar.onload=null;avatar.onerror=null;avatar.hidden=true;avatar.removeAttribute("src");fallback.hidden=false;
 const parts=String(p.display_name||"").trim().split(/\s+/).filter(Boolean);
 fallback.textContent=parts.length?parts.slice(0,2).map(part=>Array.from(part)[0]).join("").toUpperCase():"?";
 if(nativeMode&&p.avatar_available===true){avatar.onload=()=>{avatar.hidden=false;fallback.hidden=true;};avatar.onerror=()=>{avatar.hidden=true;fallback.hidden=false;};avatar.src="/dz/identity/v1/avatar";}
 const identities=$("linked-identities");identities.replaceChildren();
 for(const identity of (nativeMode?[{provider:p.identity_origin||"DragonZpyder"}]:(p.auth_identities||[]))){const chip=document.createElement("span");chip.className="identity";chip.textContent=identity.provider+(identity.account?" · "+identity.account:"");identities.append(chip)}
 const host=$("workspace-list");host.replaceChildren();
 const spaces=nativeMode?[]:await request("/api/auth/workspaces").catch(()=>[]);
 if(!Array.isArray(spaces)||spaces.length===0){const p=document.createElement("p");p.className="muted small";p.textContent=nativeMode?"Business membership is managed separately through authorized workspace access.":"No business workspaces attached to this account.";host.append(p)}
 else for(const w of spaces){const item=document.createElement("div");item.className="workspace-line";item.textContent=w.name+" · "+w.role;host.append(item)}
 show("profile");
}
(async()=>{
 const params=new URLSearchParams(location.search);
 if(["migration","migration-recovery"].includes(params.get("mode"))){
  // A separate opt-in pilot, never a fallback from failed login and never
  // an Operly session or account creation path.
  const gate=await request("/dz/import-proof/status").catch(()=>({enabled:false}));
  migrationEnabled=gate.enabled===true;
  if(migrationEnabled){
   const recovery=await request("/dz/import-proof/recovery/status").catch(()=>({enabled:false}));
   recoveryEnabled=recovery.enabled===true;
   $("migration-recovery-link").hidden=!recoveryEnabled;
   if(params.get("mode")==="migration"){show("migration");return;}
   if(recoveryEnabled){show("migration-recovery");return;}
  }
  panels.forEach(name=>{$(name+"-panel").hidden=true});
  $("mode-tabs").hidden=true;
  report("Account migration verification is not available. Return to /account for regular access.",true);
  return;
 }
 let legacyAvailable=false;
 try{const route=await request("/dz/status");nativeMode=route.web_cutover_enabled===true||route.native_session_present===true||location.pathname==="/login";legacyAvailable=route.web_cutover_enabled===false&&route.native_session_present!==true;}catch{nativeMode=true;}
 window.dragonzpyderNativeMode=nativeMode;
 window.dispatchEvent(new CustomEvent("dragonzpyder:runtime-mode",{detail:{firstParty:nativeMode}}));
 if(nativeMode){
  $("dragonzpyder-central-signin").hidden=true;
  $("legacy-login-link").hidden=location.pathname!=="/login"||!legacyAvailable;
  $("signup-form").hidden=true;
  activeRecoveryEnabled=(await request("/dz/recovery/status").catch(()=>({enabled:false}))).enabled===true;
  const forgotten=document.querySelector("[data-mode='forgot']");if(forgotten)forgotten.hidden=!activeRecoveryEnabled;
  if(activeRecoveryEnabled){const code=$("reset-code");code.minLength=43;code.maxLength=43;code.pattern="[A-Za-z0-9_-]{43}";code.inputMode="text";const label=document.querySelector("label[for='reset-code']");if(label)label.textContent="One-time recovery code";const copy=$("reset-panel").querySelector(".muted");if(copy)copy.textContent="Enter the one-time recovery code sent to your verified email.";}
 }
 if(!nativeMode) $("legacy-login-link").hidden=true;
 if(params.get("discord_error"))report(params.get("discord_error"),true);
 try{
  const sessions=nativeMode?await request("/dz/identity/v1/me"):await request("/api/auth/sessions");
  if(nativeMode?Boolean(sessions.id):(Array.isArray(sessions)&&sessions.some(s=>s?.current))){
   if(adminReturnRequested()){window.location.replace("/admin");return;}
   await profile();return;
  }
 }catch{}
 show(params.get("mode")||"login");
 // Prefer central identity when it is activated, preserving the existing
 // password/Google flow as a safe fallback until verified account cutover.
 if(!nativeMode) $("dragonzpyder-central-signin").hidden=false;
 await loadBootstrap().catch(()=>{});
 if(adminReturnRequested())report("Sign in to access your DragonZpyder admin dashboard.");
 if(params.get("email")){$("verify-email").value=params.get("email");$("reset-email").value=params.get("email")}
})().catch(e=>{show("login");report(e.message,true)});
