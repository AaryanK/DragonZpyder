/** Private, one-shot Railway Function. Uses ordinary password/session/CSRF auth.
 * Only operator-created .invalid test identities; never logs credentials/cookies.
 * Each deployment runs one explicit case; uncertain requests are never retried.
 * No provider, DB, runner or administrator credentials are needed for acceptance.
 */
const API = "https://api.dragonzpyder.xyz";
const ORIGIN = "https://dragonzpyder.xyz";
const run = Bun.env.DZ_PROBE_RUN ?? crypto.randomUUID();
const testCase = Bun.env.DZ_PROBE_CASE ?? "auth";
const email = Bun.env.DZ_PROBE_EMAIL ?? "";
const password = Bun.env.DZ_PROBE_PASSWORD ?? "";
let cookie = "";
let csrf = "";
const log = (event: object) => console.log(JSON.stringify({message:"DZ_ACCEPTANCE",run,case:testCase,at:new Date().toISOString(),...event}));

async function request(path: string, body?: unknown, authenticated = true) {
  if (!path.startsWith("/") || path.startsWith("//")) throw new Error("Invalid relative path");
  const headers: Record<string,string> = {origin:ORIGIN};
  if (body !== undefined) headers["content-type"]="application/json";
  if (authenticated) { headers.cookie=cookie; headers["x-dz-csrf"]=csrf; }
  const response=await fetch(API+path,{method:body===undefined?"GET":"POST",headers,
    body:body===undefined?undefined:JSON.stringify(body),redirect:"error",signal:AbortSignal.timeout(240000)});
  const raw=await response.text();
  if(raw.length>300000) throw new Error("Response exceeds acceptance log bound");
  let data: any;
  try {data=JSON.parse(raw);} catch {data={non_json:true,length:raw.length};}
  return {response,data};
}

async function main() {
  if(!/^acceptance-[0-9a-f-]{36}@dragonzpyder\.invalid$/.test(email) || password.length<32)
    throw new Error("Dedicated test credentials required");
  const login=await request("/identity/v1/password/login",{email,password},false);
  log({event:"login",status:login.response.status});
  if(login.response.status!==200) throw new Error("Normal password login failed");
  const cookies=login.response.headers.getSetCookie().map(x=>x.split(";",1)[0]);
  cookie=cookies.filter(x=>x.startsWith("__Host-dz_identity=")||x.startsWith("__Host-dz_csrf=")).join("; ");
  csrf=cookies.find(x=>x.startsWith("__Host-dz_csrf="))?.slice("__Host-dz_csrf=".length)??"";
  if(!csrf || !cookie.includes("__Host-dz_identity=")) throw new Error("Login did not issue session");
  const me=await request("/identity/v1/me");
  if(me.response.status!==200 || me.data.email!==email || me.data.identity_origin!=="operator_test")
    throw new Error("Unexpected test identity");
  log({event:"identity",status:me.response.status,subject:me.data.id,origin:me.data.identity_origin});
  const status=await request("/v2/personal/status");
  log({event:"capabilities",status:status.response.status,response:status.data});
  if(testCase==="auth") {
    const missing=await request("/v2/personal/conversations",undefined,false);
    const saved=csrf; csrf="invalid-csrf-test";
    const denied=await request("/v2/personal/chat",{message:"must never execute",request_id:crypto.randomUUID()});
    csrf=saved;
    log({event:"auth_boundaries",unauthenticated:missing.response.status,invalid_csrf:denied.response.status,
      verified:missing.response.status===401&&denied.response.status===401});
    return;
  }
  const prompts: Record<string,{message:string;[key:string]:unknown}>={
    chat:{message:"Reply with exactly DZ_AUTHENTICATED_HARNESS_OK. Do not call tools."},
    python:{allow_computer:true,message:"Use the isolated computer tools. Execute Python to compute sum(x*x for x in [13,29,47,61]). Write the result plus a newline to acceptance-result.txt, read it back, and publish it as a downloadable artifact. Report the actual result and tool outcome; if blocked, report the error."},
    terminal:{allow_computer:true,message:"Use computer_shell in the isolated sandbox to execute: printf 'DZ_TERMINAL_OK\\n'; id -u; pwd. Report the actual stdout and exit code."},
    research:{message:"Retrieve the actual official Python documentation for math.isqrt and explain its definition in one sentence with a citation. Include one integer example verified from the source. Do not treat a search snippet as retrieved page evidence."},
    media:{allow_media:true,message:"Generate one small image of a red circle on a white background using the authorized media tool, publish the real output, and return its downloadable artifact. Report an actual failure if unavailable."},
  };
  if(!prompts[testCase]) throw new Error("Unsupported acceptance case");
  const request_id=crypto.randomUUID();
  const payload={...prompts[testCase],request_id};
  log({event:"prompt",request_id,payload});
  const answer=await request("/v2/personal/chat",payload);
  log({event:"response",request_id,status:answer.response.status,response:answer.data});
  const receipt=await request("/v2/personal/requests/"+request_id);
  log({event:"request_readback",request_id,status:receipt.response.status,response:receipt.data});
}

try {await main();}
catch(error) {log({event:"failure",error_type:error?.constructor?.name??"Error",message:error instanceof Error?error.message.slice(0,160):"Unknown failure"});process.exitCode=1;}
finally {
  if(cookie&&csrf) {
    try {const end=await request("/identity/v1/logout",{});log({event:"logout",status:end.response.status});}
    catch {log({event:"logout_unconfirmed"});}
  }
}
