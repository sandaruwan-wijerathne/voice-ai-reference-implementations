import React from 'react';
import { LiveKitRoom, AudioConference, RoomAudioRenderer, StartAudio } from '@livekit/components-react';
import { Room, RoomEvent, Track } from 'livekit-client';
import '@livekit/components-styles';
import './App.css';

const TOKEN = process.env.REACT_APP_LIVEKIT_TOKEN;
const WS_URL = process.env.REACT_APP_LIVEKIT_SERVER_URL?process.env.REACT_APP_LIVEKIT_SERVER_URL:"ws://localhost:7880";

class App extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
          audioReady: false,
          audioError: '',
          agentAudioActive: false,
          agentConnected: false,
        };
        this.room = new Room();
        this.room.on(RoomEvent.AudioPlaybackStatusChanged, this.handleAudioPlaybackChanged);
        this.room.on(RoomEvent.TrackSubscribed, this.handleTrackSubscribed);
        this.room.on(RoomEvent.TrackUnsubscribed, this.handleTrackUnsubscribed);
        this.room.on(RoomEvent.ParticipantConnected, this.handleParticipantConnected);
        this.room.on(RoomEvent.ParticipantDisconnected, this.handleParticipantDisconnected);
    }

    componentWillUnmount() {
      this.room.off(RoomEvent.AudioPlaybackStatusChanged, this.handleAudioPlaybackChanged);
      this.room.off(RoomEvent.TrackSubscribed, this.handleTrackSubscribed);
      this.room.off(RoomEvent.TrackUnsubscribed, this.handleTrackUnsubscribed);
      this.room.off(RoomEvent.ParticipantConnected, this.handleParticipantConnected);
      this.room.off(RoomEvent.ParticipantDisconnected, this.handleParticipantDisconnected);
      this.room.disconnect();
    }

    isAgentParticipant = (participant) => participant?.identity?.startsWith('agent-');

    refreshAgentStatus = () => {
      const remoteParticipants = Array.from(this.room.remoteParticipants.values());
      const agentConnected = remoteParticipants.some((p) => this.isAgentParticipant(p));
      this.setState({ agentConnected });
    };

    handleParticipantConnected = () => {
      this.refreshAgentStatus();
    };

    handleParticipantDisconnected = () => {
      this.refreshAgentStatus();
      this.setState({ agentAudioActive: false });
    };

    handleTrackSubscribed = (track, _publication, participant) => {
      if (track.kind === Track.Kind.Audio && this.isAgentParticipant(participant)) {
        this.setState({ agentAudioActive: true });
      }
      this.refreshAgentStatus();
    };

    handleTrackUnsubscribed = (_track, _publication, participant) => {
      if (this.isAgentParticipant(participant)) {
        this.setState({ agentAudioActive: false });
      }
      this.refreshAgentStatus();
    };

    handleAudioPlaybackChanged = () => {
      this.setState({
        audioReady: this.room.canPlaybackAudio,
        audioError: this.room.canPlaybackAudio
          ? ''
          : 'Audio playback is blocked by browser. Click "Enable audio output".',
      });
    };

    handleConnected = async () => {
      this.refreshAgentStatus();
      this.handleAudioPlaybackChanged();
      await this.enableAudioOutput();
    };

    handleDisconnected = () => {
      this.setState({
        audioReady: false,
        audioError: '',
        agentAudioActive: false,
        agentConnected: false,
      });
    };

    enableAudioOutput = async () => {
      try {
        await this.room.startAudio();
        this.handleAudioPlaybackChanged();
      } catch (_err) {
        this.setState({
          audioReady: false,
          audioError: 'Audio playback is blocked by browser. Click "Enable audio output".',
        });
      }
    };

    render() {
        const { audioReady, audioError, agentAudioActive, agentConnected } = this.state;
        return (
          <div className='livekit'>
            <div className='title'>Chat with Nova Sonic via LiveKit</div>
            <div className='url'>{WS_URL}</div>
            <div className='audioControls'>
              <button className='audioButton' onClick={() => this.enableAudioOutput()}>
                Enable audio output
              </button>
              <span className='audioState'>{audioReady ? 'Audio ready' : 'Audio locked'}</span>
              <span className='audioState'>
                Agent {agentConnected ? 'connected' : 'not connected'}
              </span>
              <span className='audioState'>
                Agent audio {agentAudioActive ? 'active' : 'idle'}
              </span>
            </div>
            {audioError ? <div className='audioHint'>{audioError}</div> : null}
              <div data-lk-theme="default" >
                <LiveKitRoom
                  audio={true}
                  video={false}
                  token={TOKEN}
                  serverUrl={WS_URL}
                  connect={true}
                  room={this.room}
                  onConnected={this.handleConnected}
                  onDisconnected={this.handleDisconnected}
                >
                  <StartAudio label="Click to enable agent audio" />
                  <AudioConference />
                  <RoomAudioRenderer volume={1} muted={false} />
                </LiveKitRoom>
              </div>
          </div>
        );
    }
}

export default App;