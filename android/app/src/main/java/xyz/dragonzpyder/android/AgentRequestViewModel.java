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
    static final class Outcome {
        final String id;
        final boolean running;
        final JSONObject response;
        final Exception failure;
        Outcome(String id,boolean running,JSONObject response,Exception failure){
            this.id=id;this.running=running;this.response=response;this.failure=failure;
        }
    }
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final MutableLiveData<Outcome> state=new MutableLiveData<>();
    private long generation;
    LiveData<Outcome> outcomes(){return state;}
    Outcome current(){return state.getValue();}
    // Main-thread only; never automatically resubmit a lost request.
    void start(String id, Call work){
        Outcome current=state.getValue();
        if(current!=null&&current.running)throw new IllegalStateException("Agent request already active");
        final long attempt=++generation;
        state.setValue(new Outcome(id,true,null,null));
        worker.execute(()->{
            JSONObject result=null;Exception error=null;
            try{result=work.execute();}catch(Exception failure){error=failure;}
            final JSONObject response=result;final Exception failure=error;
            new android.os.Handler(android.os.Looper.getMainLooper()).post(()->{
                if(attempt==generation)state.setValue(new Outcome(id,false,response,failure));
            });
        });
    }
    void reset(){generation++;state.setValue(null);}
    @Override protected void onCleared(){generation++;worker.shutdown();super.onCleared();}
}
