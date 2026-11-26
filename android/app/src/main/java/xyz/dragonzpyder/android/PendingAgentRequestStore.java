package xyz.dragonzpyder.android;

import android.content.Context;
import android.content.SharedPreferences;
import java.util.UUID;

/** Local metadata only: no prompts, transcripts, credentials or tool arguments.
 * A marker can be recovered only under the same verified first-party session. */
final class PendingAgentRequestStore {
    private final SharedPreferences prefs;
    PendingAgentRequestStore(Context context){
        prefs=context.getApplicationContext().getSharedPreferences("pending_agent_request",Context.MODE_PRIVATE);
    }
    private static boolean validBinding(String value){return value!=null&&value.matches("[a-f0-9]{64}");}
    private static boolean validId(String value){
        try{return value!=null&&UUID.fromString(value).toString().equals(value);}catch(IllegalArgumentException invalid){return false;}
    }
    synchronized boolean save(String binding,String id){
        if(!validBinding(binding)||!validId(id))return false;
        return prefs.edit().putString("binding",binding).putString("request_id",id).commit();
    }
    synchronized String read(String binding){
        if(!validBinding(binding)||!binding.equals(prefs.getString("binding","")))return "";
        String id=prefs.getString("request_id","");
        return validId(id)?id:"";
    }
    synchronized boolean clear(String binding,String id){
        if(!id.equals(read(binding))||id.isEmpty())return false;
        return prefs.edit().remove("binding").remove("request_id").commit();
    }
}
