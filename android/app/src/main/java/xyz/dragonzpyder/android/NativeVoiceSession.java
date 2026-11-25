package xyz.dragonzpyder.android;

import android.content.Context;
import android.media.AudioManager;
import android.os.Handler;
import android.os.Looper;
import java.util.Collections;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import org.json.JSONObject;
import org.webrtc.*;

/** One foreground-only audio session. Provider secrets never enter Android. */
final class NativeVoiceSession {
    interface Listener { void status(String value); }
    private final DragonApi api;
    private final Context context;
    private final Listener listener;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private final String id=UUID.randomUUID().toString();
    private PeerConnectionFactory factory;
    private PeerConnection peer;
    private AudioSource source;
    private AudioTrack track;
    private DataChannel channel;
    private AudioManager audio;
    private int previousMode;
    private boolean audioChanged,closed,offered;
    private volatile boolean startAttempted;
    NativeVoiceSession(Context context,DragonApi api,Listener listener){
        this.context=context.getApplicationContext();this.api=api;this.listener=listener;
    }
    private void status(String s){if(!closed)listener.status(s);}
    private final Runnable timeout=()->{if(!closed){status("Voice timed out.");close();}};
    void start(){
        try{
            status("Connecting…");
            main.postDelayed(timeout,60000);
            audio=(AudioManager)context.getSystemService(Context.AUDIO_SERVICE);
            previousMode=audio.getMode();audio.setMode(AudioManager.MODE_IN_COMMUNICATION);audioChanged=true;
            PeerConnectionFactory.initialize(PeerConnectionFactory.InitializationOptions.builder(context).createInitializationOptions());
            factory=PeerConnectionFactory.builder().createPeerConnectionFactory();
            PeerConnection.RTCConfiguration config=new PeerConnection.RTCConfiguration(Collections.emptyList());
            config.sdpSemantics=PeerConnection.SdpSemantics.UNIFIED_PLAN;
            peer=factory.createPeerConnection(config,new PeerConnection.Observer(){
                public void onSignalingChange(PeerConnection.SignalingState state){}
                public void onIceConnectionChange(PeerConnection.IceConnectionState state){main.post(()->{
                    if(closed)return;
                    if(state==PeerConnection.IceConnectionState.CONNECTED||state==PeerConnection.IceConnectionState.COMPLETED)status("Connected · microphone live");
                    else if(state==PeerConnection.IceConnectionState.FAILED||state==PeerConnection.IceConnectionState.CLOSED){status("Voice connection ended.");close();}
                });}
                public void onIceConnectionReceivingChange(boolean receiving){}
                public void onIceGatheringChange(PeerConnection.IceGatheringState state){if(state==PeerConnection.IceGatheringState.COMPLETE)main.post(()->sendOffer());}
                public void onIceCandidate(IceCandidate c){}
                public void onIceCandidatesRemoved(IceCandidate[] candidates){}
                public void onAddStream(MediaStream stream){}
                public void onRemoveStream(MediaStream stream){}
                public void onDataChannel(DataChannel data){}
                public void onRenegotiationNeeded(){}
            });
            if(peer==null)throw new IllegalStateException("Peer unavailable");
            source=factory.createAudioSource(new MediaConstraints());
            track=factory.createAudioTrack("dragon-mic",source);
            peer.addTrack(track,Collections.singletonList("audio"));
            channel=peer.createDataChannel("oai-events",new DataChannel.Init());
            peer.createOffer(new Sdp(){
                @Override public void onCreateSuccess(SessionDescription offer){main.post(()->{
                    if(!closed&&peer!=null)peer.setLocalDescription(new Sdp(){
                        @Override public void onSetSuccess(){main.post(()->{if(!closed&&peer!=null&&peer.iceGatheringState()==PeerConnection.IceGatheringState.COMPLETE)sendOffer();});}
                    },offer);
                });}
            },new MediaConstraints());
        }catch(Exception|LinkageError failure){status("Native voice initialization failed.");close();}
    }
    private abstract class Sdp implements SdpObserver {
        public void onCreateSuccess(SessionDescription s){}
        public void onSetSuccess(){}
        public void onCreateFailure(String error){main.post(()->{status("Voice negotiation failed.");close();});}
        public void onSetFailure(String error){onCreateFailure(error);}
    }
    private void sendOffer(){
        if(closed||offered||peer==null||peer.getLocalDescription()==null)return;
        offered=true;
        String sdp=peer.getLocalDescription().description;
        io.execute(()->{
            try{
                startAttempted=true;
                JSONObject response=(JSONObject)api.call("/dz/v2/personal/voice/start",new JSONObject().put("session_id",id).put("sdp",sdp));
                if(!id.equals(response.optString("session_id")))throw new IllegalStateException("Voice session mismatch");
                String answer=response.getString("sdp");
                int duration=Math.max(1,Math.min(600,response.optInt("duration_seconds",300)));
                main.post(()->{
                    if(closed||peer==null)return;
                    peer.setRemoteDescription(new Sdp(){
                        @Override public void onSetSuccess(){main.post(()->{if(!closed){main.removeCallbacks(timeout);main.postDelayed(timeout,duration*1000L);status("Audio negotiated · connecting");}});}
                    },new SessionDescription(SessionDescription.Type.ANSWER,answer));
                });
            }catch(Exception failure){main.post(()->{status("Voice setup failed or unconfirmed. No automatic retry.");close();});}
        });
    }
    void mute(boolean value){if(!closed&&track!=null){track.setEnabled(!value);status(value?"Microphone muted":"Microphone live");}}
    void close(){
        if(closed)return;closed=true;main.removeCallbacks(timeout);
        if(track!=null)track.setEnabled(false);
        if(channel!=null){channel.close();channel.dispose();channel=null;}
        if(peer!=null){peer.close();peer.dispose();peer=null;}
        if(track!=null){track.dispose();track=null;}
        if(source!=null){source.dispose();source=null;}
        if(factory!=null){factory.dispose();factory=null;}
        if(audioChanged&&audio!=null)audio.setMode(previousMode);
        // Queue behind an in-flight start; the server also reconciles expired calls.
        io.execute(()->{if(startAttempted){try{api.call("/dz/v2/personal/voice/"+id+"/end",new JSONObject());}catch(Exception unconfirmed){main.post(()->listener.status("Microphone closed; server hangup not confirmed."));}}});
        io.shutdown();
    }
}
