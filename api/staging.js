const $=id=>document.getElementById(id);
async function refresh(){
  try{
    const r=await fetch("/status",{cache:"no-store"}); const data=await r.json();
    const list=$("status");list.replaceChildren();
    for(const [name,state] of Object.entries(data.components)){
      const item=document.createElement("div");item.className="item";
      const a=document.createElement("span");a.textContent=name.replaceAll("_"," ");
      const b=document.createElement("span");b.className="value";b.textContent=state.replaceAll("_"," ");
      item.append(a,b);list.append(item);
    }
    const harnessNote=data.harness_ready?"Harness initialized.":"Harness cannot start until test configuration is complete.";
    const keyNote=" OpenRouter key check: "+String(data.openrouter_key_validation||"not checked").replaceAll("_"," ")+".";
    $("note").textContent=harnessNote+keyNote;

  }catch(e){$("note").textContent="Cannot load status: "+e.message}
}
$("refresh").addEventListener("click",refresh);
$("run").addEventListener("click",async()=>{
  $("run").disabled=true;$("output").textContent="Running…";
  try{
    const r=await fetch("/test",{method:"POST",headers:{"content-type":"application/json","x-staging-password":$("password").value},body:JSON.stringify({thread_id:$("thread").value,prompt:$("prompt").value})});
    const data=await r.json();$("output").textContent=r.ok?data.answer:(data.detail||"Test failed");
  }catch(e){$("output").textContent="Network problem: "+e.message}
  finally{$("run").disabled=false}
});
refresh();
