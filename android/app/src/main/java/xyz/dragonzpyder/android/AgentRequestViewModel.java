package xyz.dragonzpyder.android;

import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.json.JSONObject;

/** Retains an in-flight first-party request across Activity recreation.
 * No Activity, View, credential, or automatic replay is retained here. */
public final class AgentRequestViewModel extends ViewModel {
    interface Call { JSONObject execute() throws Exception; }
    interface StreamCall { JSONObject execute(DragonApi.AgentProgress progress) throws Exception; }
    static final class Outcome {
        final String id;
        final boolean running;
        final JSONObject response;
        final Exception failure;
        final boolean streaming;
        final String partial,phase;
        Outcome(String id,boolean running,JSONObject response,Exception failure,boolean streaming,String partial,String phase){
            this.id=id;this.running=running;this.response=response;this.failure=failure;this.streaming=streaming;this.partial=partial;this.phase=phase;
        }
    }
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final MutableLiveData<Outcome> state=new MutableLiveData<>();
    private long generation;
    private final android.os.Handler main=new android.os.Handler(android.os.Looper.getMainLooper());
    LiveData<Outcome> outcomes(){return state;}
    Outcome current(){return state.getValue();}
    // Main-thread only; never automatically resubmit a lost request.
    void start(String id, Call work){startInternal(id,false,progress->work.execute());}
    void startStreaming(String id,StreamCall work){startInternal(id,true,work);}
    private void startInternal(String id,boolean streaming,StreamCall work){
        Outcome current=state.getValue();
        if(current!=null&&current.running)throw new IllegalStateException("Agent request already active");
        final long attempt=++generation;
        state.setValue(new Outcome(id,true,null,null,streaming,"",""));
        worker.execute(()->{
            JSONObject result=null;Exception error=null;
            StringBuilder partial=new StringBuilder();
            String[] phase={""};long[] last={0};
            try{result=work.execute((type,value)->{
                if("reset".equals(type))partial.setLength(0);
                else if("phase".equals(type))phase[0]=value;
                else if("delta".equals(type)&&partial.length()<100000)partial.append(value,0,Math.min(value.length(),100000-partial.length()));
                long now=android.os.SystemClock.elapsedRealtime();
                if("delta".equals(type)&&now-last[0]<50)return;
                last[0]=now;
                final String draft=partial.toString(),label=phase[0];
                main.post(()->{if(attempt==generation)state.setValue(new Outcome(id,true,null,null,streaming,draft,label));});
            });}catch(Exception failure){error=failure;}
            final JSONObject response=result;final Exception failure=error;
            main.post(()->{
                if(attempt==generation)state.setValue(new Outcome(id,false,response,failure,streaming,"",""));
            });
        });
    }
    void reset(){generation++;state.setValue(null);}
    @Override protected void onCleared(){generation++;worker.shutdown();super.onCleared();}
}
