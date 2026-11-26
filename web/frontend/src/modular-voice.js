import { Room, RoomEvent, Track } from "livekit-client";

export async function connectModularVoice({url, token, track, audio, onData, onRemote, onDisconnect}) {
  const room = new Room({adaptiveStream: true, dynacast: true});
  room.on(RoomEvent.TrackSubscribed, (remote) => {
    if (remote.kind !== Track.Kind.Audio) return;
    remote.attach(audio);
    onRemote(new MediaStream([remote.mediaStreamTrack]));
    void room.startAudio().catch(() => {});
  });
  room.on(RoomEvent.DataReceived, (bytes, participant, _kind, topic) => {
    if (topic !== "dz.voice" || !participant || participant.identity === room.localParticipant.identity) return;
    if (bytes.length > 65536) return;
    try { onData(JSON.parse(new TextDecoder().decode(bytes))); } catch {}
  });
  room.on(RoomEvent.Disconnected, onDisconnect);
  try {
    await room.connect(url, token, {autoSubscribe: true});
    await room.localParticipant.publishTrack(track, {source: Track.Source.Microphone});
    return room;
  } catch (error) {
    await room.disconnect();
    throw error;
  }
}
