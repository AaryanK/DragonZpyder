const $ = (id) => document.getElementById(id);
const panels = ["login","signup","verify","forgot","reset","profile"];
let mode = "login", bootstrap = null, challenge = null, processing = false, initializedGoogle = false;
const messageBox = $("account-message");
function report(message,isError=false){messageBox.textContent=String(message||"");messageBox.classList.toggle("error",isError);messageBox.hidden=!message;}
function show(next){if(!panels.includes(next))next="login";mode=next;report("");panels.forEach(name=>{$(name+"-panel").hidden=name!==next});$("mode-tabs").hidden=!["login","signup"].includes(next);document.querySelectorAll("[data-mode]").forEach(el=>el.classList.toggle("selected",el.dataset.mode===next));if(next==="login")loadGoogle().catch(()=>{});}
function cookie(name){const part=document.cookie.split(";").map(v=>v.trim()).find(v=>v.startsWith(name+"="));return part?decodeURIComponent(part.slice(name.length+1)):"";}
function csrf(){return cookie("__Host-operly_csrf")||cookie("operly_csrf")||bootstrap?.csrf_token||"";}
async function loadBootstrap(){bootstrap=await request("/api/auth/bootstrap",{method:"GET",unauth:true});return bootstrap;}
async function request(path,{method="GET",body,unauth=false}={}){
 const headers={accept:"application/json"};
 if(body!==undefined)headers["content-type"]="application/json";
 if(method!=="GET"&&method!=="HEAD"){headers["X-CSRF-Token"]=csrf();}
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
function authenticated(){window.location.replace("/app")}
async function ensurePersonal(){
 let response=await request("/api/auth/sessions");
 const current=Array.isArray(response)?response.find(item=>item?.current):null;
 if(!current)throw Error("Could not establish your session.");
 if(current.scope!=="personal"){await request("/api/auth/personal-scope",{method:"POST",body:{}});response=await request("/api/auth/sessions");if(!Array.isArray(response)||!response.some(item=>item?.current&&item.scope==="personal"))throw Error("Personal session unavailable.")}
}
async function afterSignIn(){await ensurePersonal();authenticated();}
async function googleCredential(credential){
 if(!credential||processing)return;
 processing=true;report("");
 try{
  await request("/api/auth/google",{method:"POST",body:{credential}});
  await afterSignIn();
 }catch(e){report(e.message||"Google sign-in failed.",true)}finally{processing=false}
}
async function loadGoogle(){
 if(mode!=="login"||initializedGoogle)return;
 const g=bootstrap||await loadBootstrap();
 if(!g.google_client_id||!g.google_nonce)return;
 const render=()=>{if(!window.google?.accounts?.id||initializedGoogle)return;
  const host=$("google-provider");host.hidden=false;
  window.google.accounts.id.initialize({client_id:g.google_client_id,nonce:g.google_nonce,callback:result=>googleCredential(String(result?.credential||"")),auto_select:false,cancel_on_tap_outside:true});
  window.google.accounts.id.renderButton(host,{theme:"filled_black",size:"large",text:"continue_with",shape:"rectangular",width:Math.min(360,Math.max(220,host.clientWidth||300))});initializedGoogle=true;
 };
 if(window.google?.accounts?.id){render();return;}
 const script=document.createElement("script");script.src="https://accounts.google.com/gsi/client";script.async=true;script.defer=true;script.onload=render;script.onerror=()=>report("Google sign-in could not load; use email to continue.",true);document.head.append(script);
}
document.querySelectorAll("[data-mode]").forEach(el=>el.addEventListener("click",()=>show(el.dataset.mode)));
$("login-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 await loadBootstrap();
 try{await request("/api/auth/login",{method:"POST",body:{email:$("login-email").value.trim(),password:$("login-password").value}});await afterSignIn()}
 catch(err){if(err.code==="EMAIL_NOT_VERIFIED"){challenge={email:$("login-email").value.trim()};$("verify-email").value=challenge.email;show("verify");report("Please verify your email to continue.");return;}throw err}
})});
$("signup-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
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
 await loadBootstrap();await request("/api/auth/forgot-password",{method:"POST",body:{email:$("forgot-email").value.trim()}});
 $("reset-email").value=$("forgot-email").value.trim();show("reset");report("If the account exists, password reset instructions were sent.");
})});
$("reset-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 await loadBootstrap();await request("/api/auth/reset-password",{method:"POST",body:{email:$("reset-email").value.trim(),code:$("reset-code").value.trim(),password:$("reset-password").value}});
 show("login");report("Password updated. Sign in with your new password.");
})});
$("profile-form").addEventListener("submit",e=>{e.preventDefault();submitAction(e.currentTarget,async()=>{
 await request("/api/auth/me",{method:"PATCH",body:{display_name:$("profile-name").value.trim()}});report("Your account has been updated.");
})});
$("account-logout").addEventListener("click",async()=>{try{await request("/api/auth/logout",{method:"POST",body:{}});window.location.replace("/account")}catch(e){report(e.message,true)}});
async function profile(){
 const p=await request("/api/auth/me");$("profile-email").textContent=p.email||"";$("profile-name").value=p.display_name||"";
 const identities=$("linked-identities");identities.replaceChildren();
 for(const identity of p.auth_identities||[]){const chip=document.createElement("span");chip.className="identity";chip.textContent=identity.provider+(identity.account?" · "+identity.account:"");identities.append(chip)}
 const host=$("workspace-list");host.replaceChildren();
 const spaces=await request("/api/auth/workspaces").catch(()=>[]);
 if(!Array.isArray(spaces)||spaces.length===0){const p=document.createElement("p");p.className="muted small";p.textContent="No business workspaces attached to this account.";host.append(p)}
 else for(const w of spaces){const item=document.createElement("div");item.className="workspace-line";item.textContent=w.name+" · "+w.role;host.append(item)}
 show("profile");
}
(async()=>{
 const params=new URLSearchParams(location.search);
 if(params.get("discord_error"))report(params.get("discord_error"),true);
 try{
  const sessions=await request("/api/auth/sessions");
  if(Array.isArray(sessions)&&sessions.some(s=>s?.current)){
   await profile();return;
  }
 }catch{}
 show(params.get("mode")||"login");
 if(params.get("email")){$("verify-email").value=params.get("email");$("reset-email").value=params.get("email")}
})().catch(e=>{show("login");report(e.message,true)});
