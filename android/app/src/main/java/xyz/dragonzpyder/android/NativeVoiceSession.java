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
import org.json.JSONArray;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import org.webrtc.*;

/** One foreground-only audio session. Provider secrets never enter Android. */
final class NativeVoiceSession {
    interface Listener {
        void status(String value);
        default void transcript(String speaker,String value){}
        default void agentResult(String prompt,JSONObject result){}
    }
    private final DragonApi api;
    private final Context context;
    private final Listener listener;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private final String id=UUID.randomUUID().toString();
    private final String binding,conversationId;
    private final JSONArray aliases;
    private final boolean agentMode;
    private final HashSet<String> completedEvents=new HashSet<>();
    private boolean agentBusy,awaitingPlayback;
    private PeerConnectionFactory factory;
    private PeerConnection peer;
    private AudioSource source;
    private AudioTrack track;
    private DataChannel channel;
    private AudioManager audio;
    private int previousMode;
    private boolean audioChanged,offered,muted,connected;
    private volatile boolean closed;
    private volatile boolean startAttempted;
    NativeVoiceSession(Context context,DragonApi api,boolean agentMode,String conversationId,JSONArray aliases,Listener listener){
        this.context=context.getApplicationContext();this.api=api;this.listener=listener;
        this.binding=api.pendingRequestBinding();this.agentMode=agentMode;this.conversationId=conversationId;this.aliases=aliases;
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
                    if(state==PeerConnection.IceConnectionState.CONNECTED||state==PeerConnection.IceConnectionState.COMPLETED){connected=true;status(muted?"Microphone muted":"Ready · microphone live");}
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
            if(channel!=null)channel.registerObserver(new DataChannel.Observer(){
                public void onBufferedAmountChange(long previousAmount){}
                public void onStateChange(){}
                public void onMessage(DataChannel.Buffer buffer){
                    if(buffer.binary||buffer.data.remaining()>65536)return;
                    try{
                        byte[] bytes=new byte[buffer.data.remaining()];buffer.data.get(bytes);
                        JSONObject event=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
                        main.post(()->onProviderEvent(event));
                    }catch(Exception malformed){/* Never log provider payloads. */}
                }
            });
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
                if(closed)return;
                JSONObject body=new JSONObject().put("session_id",id).put("sdp",sdp);
                if(agentMode){body.put("agent_mode",true);if(!conversationId.isEmpty())body.put("conversation_id",conversationId);body.put("mcp_connection_ids",aliases);}
                startAttempted=true;
                JSONObject response=(JSONObject)api.boundVoiceCall(binding,"/dz/v2/personal/voice/start",body);
                if(!id.equals(response.optString("session_id"))||agentMode!=response.optBoolean("agent_mode",false))throw new IllegalStateException("Voice session mismatch");
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
    // Only completed user transcript events can enter the canonical harness.
    // Provider output never executes tools. No automatic retry of uncertain turns.
    private void handleAgentTranscript(JSONObject event){
        String eventId=event.optString("item_id"),prompt=event.optString("transcript").trim();
        if(!agentMode||muted||agentBusy||!eventId.matches("[A-Za-z0-9_-]{1,180}")||prompt.isEmpty()||prompt.length()>12000||completedEvents.size()>=128||!completedEvents.add(eventId))return;
        agentBusy=true;awaitingPlayback=false;if(track!=null)track.setEnabled(false);
        status("Working through DragonZpyder…");
        io.execute(()->{
            try{
                if(closed)return;
                JSONObject result=(JSONObject)api.boundVoiceCall(binding,"/dz/v2/personal/voice/"+id+"/turn",new JSONObject().put("event_id",eventId).put("transcript",prompt));
                String answer=result.optString("message");
                UUID.fromString(result.getString("conversation_id"));
                if(answer.isEmpty())throw new IllegalStateException("No confirmed agent response");
                main.post(()->{
                    if(closed||!binding.equals(api.pendingRequestBinding()))return;
                    listener.agentResult(prompt,result);
                    listener.transcript("DragonZpyder",answer);
                    try{
                        JSONObject speech=new JSONObject().put("type","response.create").put("response",new JSONObject()
                            .put("conversation","none").put("instructions","Read the supplied answer naturally without adding facts, claims or actions.")
                            .put("input",new JSONArray().put(new JSONObject().put("type","message").put("role","user")
                            .put("content",new JSONArray().put(new JSONObject().put("type","input_text").put("text",answer.substring(0,Math.min(10000,answer.length()))))))));
                        if(channel==null||channel.state()!=DataChannel.State.OPEN||!channel.send(new DataChannel.Buffer(ByteBuffer.wrap(speech.toString().getBytes(StandardCharsets.UTF_8)),false)))throw new IllegalStateException("Voice playback unavailable");
                        awaitingPlayback=true;status("Reading the agent result…");
                    }catch(Exception failure){status("Answer saved in chat; speech unavailable.");close();}
                });
            }catch(Exception failure){main.post(()->{if(!closed){listener.transcript("DragonZpyder","The request outcome is unconfirmed. Check conversation history before repeating it.");status("Voice request unconfirmed.");close();}});}
        });
    }
    private void finishPlayback(){awaitingPlayback=false;agentBusy=false;if(track!=null)track.setEnabled(!muted);status(muted?"Microphone muted":"Ready · microphone live");}
    private void onProviderEvent(JSONObject event){
        if(closed||!connected||!binding.equals(api.pendingRequestBinding()))return;
        String type=event.optString("type");
        if(type.equals("conversation.item.input_audio_transcription.completed")){
            String words=event.optString("transcript");if(!words.isEmpty())listener.transcript("You",words);
            handleAgentTranscript(event);
        }
        if(!agentMode&&(type.equals("response.output_audio_transcript.done")||type.equals("response.audio_transcript.done"))){
            String words=event.optString("transcript");if(!words.isEmpty())listener.transcript("DragonZpyder",words);
        }
        switch(type){
            case "input_audio_buffer.speech_started":if(!muted)status("Listening…");break;
            case "input_audio_buffer.speech_stopped":if(!muted)status("Thinking…");break;
            case "output_audio_buffer.started":if(!agentMode||awaitingPlayback)status("Speaking…");break;
            case "output_audio_buffer.stopped":
            case "output_audio_buffer.cleared":if(agentMode){if(awaitingPlayback)finishPlayback();}else status(muted?"Microphone muted":"Ready · microphone live");break;
            case "error":status("Voice provider reported an error.");if(agentBusy)close();break;
            default:break;
        }
    }
    void mute(boolean value){if(!closed&&track!=null){muted=value;track.setEnabled(!value&&!agentBusy);status(value?"Microphone muted":agentBusy?"Working through DragonZpyder…":connected?"Ready · microphone live":"Connecting…");}}
    void close(){
        if(closed)return;closed=true;main.removeCallbacks(timeout);
        if(track!=null)track.setEnabled(false);
        if(channel!=null){channel.unregisterObserver();channel.close();channel.dispose();channel=null;}
        if(peer!=null){peer.close();peer.dispose();peer=null;}
        if(track!=null){track.dispose();track=null;}
        if(source!=null){source.dispose();source=null;}
        if(factory!=null){factory.dispose();factory=null;}
        if(audioChanged&&audio!=null)audio.setMode(previousMode);
        // Queue behind an in-flight start; the server also reconciles expired calls.
        io.execute(()->{if(startAttempted){try{api.boundVoiceCall(binding,"/dz/v2/personal/voice/"+id+"/end",new JSONObject());}catch(Exception unconfirmed){main.post(()->listener.status("Microphone closed; server hangup not confirmed."));}}});
        io.shutdown();
    }
}
