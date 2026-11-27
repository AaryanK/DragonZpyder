const $ = (id) => document.getElementById(id);
const panels = ["login","signup","forgot","reset","profile","migration","migration-recovery"];
let mode = "login", processing = false;
// DragonZpyder owns account access, independently of runtime cutover.
const nativeMode = true;
let googleRenderedMode = null, nativeGoogleState = null;
let migrationEnabled = false, recoveryEnabled = false, recoveryEmail = null;
let activeRecoveryEnabled=false;
const messageBox = $("account-message");
function report(message,isError=false){messageBox.textContent=String(message||"");messageBox.classList.toggle("error",isError);messageBox.hidden=!message;}
function show(next){if(!panels.includes(next))next="login";if(next==="migration"&&!migrationEnabled)next="login";if(next==="migration-recovery"&&!recoveryEnabled)next="login";if(nativeMode&&!["login","signup","profile","migration","migration-recovery",...(activeRecoveryEnabled?["forgot","reset"]:[])].includes(next))next="login";mode=next;report("");panels.forEach(name=>{$(name+"-panel").hidden=name!==next});$("mode-tabs").hidden=!["login","signup"].includes(next);document.querySelectorAll("[data-mode]").forEach(el=>el.classList.toggle("selected",el.dataset.mode===next));if(next==="login"||(nativeMode&&next==="signup")||next==="migration")loadGoogle().catch(()=>{});}
function cookie(name){const part=document.cookie.split(";").map(v=>v.trim()).find(v=>v.startsWith(name+"="));return part?decodeURIComponent(part.slice(name.length+1)):"";}
function csrf(){return cookie("__Host-dz_csrf");}
async function request(path,{method="GET",body,unauth=false}={}){
 const headers={accept:"application/json"};
 if(body!==undefined)headers["content-type"]="application/json";
 if(method!=="GET"&&method!=="HEAD"){
  headers["X-DZ-CSRF"]=csrf();
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
async function ensurePersonal(){await request("/dz/identity/v1/me");}
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
  {
   if(!nativeGoogleState?.state)throw Error("Google sign-in challenge expired. Retry.");
   const action=mode==="signup"?"signup":"complete";
   await request("/dz/identity/v1/provider/google/"+action,{method:"POST",body:{state:nativeGoogleState.state,credential}});
   nativeGoogleState=null;
  }
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
 {
  if(googleRenderedMode===mode)return;
  const g=await request("/dz/identity/v1/provider/google/start",{method:"POST"});
  nativeGoogleState=g;
  if(!g.client_id||!g.nonce)return;
  return renderGoogle(g.client_id,g.nonce,mode==="signup"?"google-provider-signup":"google-provider");
 }
}
function renderGoogle(clientId,nonce,hostId){
 const expectedMode=mode;
 const render=()=>{if(mode!==expectedMode||!window.google?.accounts?.id)return;
  const host=$(hostId);host.hidden=false;
  window.google.accounts.id.initialize({client_id:clientId,nonce,callback:result=>googleCredential(String(result?.credential||""),expectedMode),auto_select:false,cancel_on_tap_outside:true});
  host.replaceChildren();
  window.google.accounts.id.renderButton(host,{theme:"outline",size:"large",text:"continue_with",shape:"rectangular",width:Math.min(400,Math.max(200,Math.floor(host.clientWidth||300)))});
  googleRenderedMode=mode;
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
 await request("/dz/identity/v1/password/login",{method:"POST",body:{email:$("login-email").value.trim(),password:$("login-password").value}});
 await afterSignIn();
})});
$("forgot-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 if(!activeRecoveryEnabled)throw Error("Password recovery is unavailable.");await request("/dz/identity/v1/recovery/start",{method:"POST",body:{email:$("forgot-email").value.trim()}});
 $("reset-email").value=$("forgot-email").value.trim();show("reset");report("If the account exists, password reset instructions were sent.");
})});
$("reset-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 if(!activeRecoveryEnabled)throw Error("Password recovery is unavailable.");const password=$("reset-password").value;const code=$("reset-code").value.trim();$("reset-password").value="";$("reset-code").value="";await request("/dz/identity/v1/recovery/complete",{method:"POST",body:{email:$("reset-email").value.trim(),code,password}});
 show("login");report("Password updated. Sign in with your new password.");
})});
$("profile-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 await request("/dz/identity/v1/me",{method:"PATCH",body:{display_name:$("profile-name").value.trim()}});report("Your account has been updated.");
})});
$("account-logout").addEventListener("click",async()=>{try{await request("/dz/identity/v1/logout",{method:"POST",body:{}});window.location.replace("/login")}catch(e){report(e.message,true)}});
async function profile(){
 const p=await request("/dz/identity/v1/me");$("profile-email").textContent=p.email||"";$("profile-name").value=p.display_name||"";
 const avatar=$("account-profile-avatar"), fallback=$("account-profile-fallback");
 avatar.onload=null;avatar.onerror=null;avatar.hidden=true;avatar.removeAttribute("src");fallback.hidden=false;
 const parts=String(p.display_name||"").trim().split(/\s+/).filter(Boolean);
 fallback.textContent=parts.length?parts.slice(0,2).map(part=>Array.from(part)[0]).join("").toUpperCase():"?";
 if(nativeMode&&p.avatar_available===true){avatar.onload=()=>{avatar.hidden=false;fallback.hidden=true;};avatar.onerror=()=>{avatar.hidden=true;fallback.hidden=false;};avatar.src="/dz/identity/v1/avatar";}
 const identities=$("linked-identities");identities.replaceChildren();
 for(const identity of [{provider:p.identity_origin||"DragonZpyder"}]){const chip=document.createElement("span");chip.className="identity";chip.textContent=identity.provider+(identity.account?" · "+identity.account:"");identities.append(chip)}
 const host=$("workspace-list");host.replaceChildren();
 const note=document.createElement("p");note.className="muted small";note.textContent="Business workspace access is managed separately.";host.append(note);
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
 window.dragonzpyderNativeMode=true;
 window.dispatchEvent(new CustomEvent("dragonzpyder:runtime-mode",{detail:{firstParty:true}}));
 activeRecoveryEnabled=(await request("/dz/recovery/status").catch(()=>({enabled:false}))).enabled===true;
 const forgotten=document.querySelector("[data-mode='forgot']");if(forgotten)forgotten.hidden=!activeRecoveryEnabled;
 if(activeRecoveryEnabled){const code=$("reset-code");code.minLength=43;code.maxLength=43;code.pattern="[A-Za-z0-9_-]{43}";code.inputMode="text";const label=document.querySelector("label[for='reset-code']");if(label)label.textContent="One-time recovery code";const copy=$("reset-panel").querySelector(".muted");if(copy)copy.textContent="Enter the one-time recovery code sent to your verified email.";}
 if(params.get("discord_error"))report(params.get("discord_error"),true);
 try{
  const session=await request("/dz/identity/v1/me");
  if(Boolean(session.id)){
   if(adminReturnRequested()){window.location.replace("/admin");return;}
   await profile();return;
  }
 }catch{}
 show(params.get("mode")||"login");
 if(adminReturnRequested())report("Sign in to access your DragonZpyder admin dashboard.");
 if(params.get("email"))$("reset-email").value=params.get("email");
})().catch(e=>{show("login");report(e.message,true)});
