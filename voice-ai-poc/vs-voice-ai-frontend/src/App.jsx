import { useState, useEffect, useRef } from 'react'
import './App.css'

const BUFFER_SIZE = 4800

// Player class for audio playback
class Player {
  constructor() {
    this.playbackNode = null
    this.audioContext = null
  }

  async init(sampleRate) {
    this.audioContext = new AudioContext({ sampleRate })
    await this.audioContext.audioWorklet.addModule('/static/audio-playback-worklet.js')

    this.playbackNode = new AudioWorkletNode(this.audioContext, 'audio-playback-worklet')
    this.playbackNode.connect(this.audioContext.destination)
  }

  play(buffer) {
    if (this.playbackNode) {
      this.playbackNode.port.postMessage(buffer)
    }
  }

  stop() {
    if (this.playbackNode) {
      this.playbackNode.port.postMessage(null)
    }
  }

  async close() {
    if (this.audioContext) {
      await this.audioContext.close()
      this.audioContext = null
    }
    this.playbackNode = null
  }
}

// Recorder class for audio capture
class Recorder {
  constructor(onDataAvailable) {
    this.onDataAvailable = onDataAvailable
    this.audioContext = null
    this.mediaStream = null
    this.mediaStreamSource = null
    this.workletNode = null
  }

  async start(stream) {
    try {
      if (this.audioContext) {
        await this.audioContext.close()
      }

      this.audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 })

      await this.audioContext.audioWorklet.addModule('/static/audio-processor-worklet.js')

      this.mediaStream = stream
      this.mediaStreamSource = this.audioContext.createMediaStreamSource(this.mediaStream)

      this.workletNode = new AudioWorkletNode(this.audioContext, 'audio-processor-worklet')
      this.workletNode.port.onmessage = (event) => {
        this.onDataAvailable(event.data.buffer)
      }

      this.mediaStreamSource.connect(this.workletNode)
      this.workletNode.connect(this.audioContext.destination)
    } catch (error) {
      console.error('Error starting recorder:', error)
      this.stop()
      throw error
    }
  }

  async stop() {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop())
      this.mediaStream = null
    }

    if (this.audioContext) {
      await this.audioContext.close()
      this.audioContext = null
    }

    this.mediaStreamSource = null
    this.workletNode = null
  }
}

function App() {
  const [isConnected, setIsConnected] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [conversationActive, setConversationActive] = useState(false)
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('api_key') || '')
  const [showApiKeyInput, setShowApiKeyInput] = useState(() => !localStorage.getItem('api_key'))
  const [audioLevel, setAudioLevel] = useState(0)
  const [analyserReady, setAnalyserReady] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState('novasonic')
  const wsRef = useRef(null)
  const playerRef = useRef(null)
  const recorderRef = useRef(null)
  const audioBufferRef = useRef(new Uint8Array())
  const analyserRef = useRef(null)
  const analyserContextRef = useRef(null)
  const animationFrameRef = useRef(null)
  const mediaStreamRef = useRef(null)

  const baseWS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/voice/browser/media-stream'

  const getWebSocketURL = () => {
    if (selectedProvider === 'assemblyai') {
      return baseWS_URL + '-assemblyai'
    }
    if (selectedProvider === 'gemini-flash') {  
      return baseWS_URL + '-gemini-flash'
    }
    if (selectedProvider === 'novasonic') {
      return baseWS_URL + '-novasonic'
    }
    return baseWS_URL
  }

  useEffect(() => {
    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (playerRef.current) {
        playerRef.current.close()
      }
      if (recorderRef.current) {
        recorderRef.current.stop()
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
      if (analyserRef.current) {
        analyserRef.current = null
      }
      if (analyserContextRef.current) {
        analyserContextRef.current.close()
        analyserContextRef.current = null
      }
    }
  }, [])

  // Audio level monitoring effect
  useEffect(() => {
    if (!conversationActive || !analyserRef.current || !analyserReady) {
      setAudioLevel(0)
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = null
      }
      return
    }

    const updateAudioLevel = () => {
      if (!analyserRef.current || !conversationActive) {
        setAudioLevel(0)
        return
      }

      try {
        // Use time domain data for accurate level detection
        const bufferLength = analyserRef.current.fftSize
        const dataArray = new Uint8Array(bufferLength)
        analyserRef.current.getByteTimeDomainData(dataArray)

        // Calculate peak and RMS for more accurate level
        let sum = 0
        let peak = 0
        for (let i = 0; i < dataArray.length; i++) {
          const normalized = Math.abs((dataArray[i] - 128) / 128)
          sum += normalized * normalized
          peak = Math.max(peak, normalized)
        }
        const rms = Math.sqrt(sum / dataArray.length)
        
        // Use a combination of peak and RMS, weighted towards peak for responsiveness
        const level = Math.min(100, Math.max(0, (peak * 0.7 + rms * 0.3) * 150))
        setAudioLevel(level)

        animationFrameRef.current = requestAnimationFrame(updateAudioLevel)
      } catch (error) {
        console.error('Error reading audio level:', error)
        setAudioLevel(0)
      }
    }

    // Small delay to ensure analyser is fully initialized
    const timeoutId = setTimeout(() => {
      updateAudioLevel()
    }, 100)

    return () => {
      clearTimeout(timeoutId)
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = null
      }
    }
  }, [conversationActive, analyserReady])

  const handleApiKeySubmit = (e) => {
    e.preventDefault()
    if (apiKey.trim()) {
      localStorage.setItem('api_key', apiKey.trim())
      setShowApiKeyInput(false)
    }
  }

  const handleApiKeyChange = () => {
    const newApiKey = prompt('Enter your Key:')
    if (newApiKey !== null) {
      if (newApiKey.trim()) {
        setApiKey(newApiKey.trim())
        localStorage.setItem('api_key', newApiKey.trim())
      } else {
        // Clear API key
        setApiKey('')
        localStorage.removeItem('api_key')
        setShowApiKeyInput(true)
      }
    }
  }

  const handleDeleteKey = () => {
    if (window.confirm('Are you sure you want to delete your API key?')) {
      setApiKey('')
      localStorage.removeItem('api_key')
      setShowApiKeyInput(true)
    }
  }

  const appendToBuffer = (newData) => {
    const newBuffer = new Uint8Array(audioBufferRef.current.length + newData.length)
    newBuffer.set(audioBufferRef.current)
    newBuffer.set(newData, audioBufferRef.current.length)
    audioBufferRef.current = newBuffer
  }

  const handleAudioData = (data) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return
    }

    const uint8Array = new Uint8Array(data)
    appendToBuffer(uint8Array)

    // Send audio when buffer reaches BUFFER_SIZE
    if (audioBufferRef.current.length >= BUFFER_SIZE) {
      const toSend = new Uint8Array(audioBufferRef.current.slice(0, BUFFER_SIZE))
      audioBufferRef.current = new Uint8Array(audioBufferRef.current.slice(BUFFER_SIZE))

      // Convert to base64
      const regularArray = Array.from(toSend)
      const base64 = btoa(String.fromCharCode(...regularArray))

      // Send as JSON message
      wsRef.current.send(JSON.stringify({
        type: 'input_audio_buffer.append',
        audio: base64
      }))
    }
  }

  const connectWebSocket = async () => {
    try {
      // Check if API key is available
      const currentApiKey = localStorage.getItem('api_key')
      if (!currentApiKey) {
        alert('Please enter your Key first')
        setShowApiKeyInput(true)
        return
      }

      // Initialize audio player first
      const audioPlayer = new Player()
      await audioPlayer.init(24000)
      playerRef.current = audioPlayer

      // Build WebSocket URL with API key as query parameter
      // Browsers don't support custom headers for WebSocket, so we use query parameter
      const wsURL = getWebSocketURL()
      const url = new URL(wsURL)
      url.searchParams.set('api_key', currentApiKey)
      const ws = new WebSocket(url.toString())
      wsRef.current = ws

      const handleOpen = async () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        setConversationActive(true)

        // Start microphone capture
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
          mediaStreamRef.current = stream
          
          // Create analyser node for audio level monitoring
          // Use a separate AudioContext for the analyser to avoid conflicts
          const audioContext = new (window.AudioContext || window.webkitAudioContext)()
          analyserContextRef.current = audioContext
          
          // Resume context if suspended (required by some browsers)
          if (audioContext.state === 'suspended') {
            await audioContext.resume()
          }
          
          const analyser = audioContext.createAnalyser()
          analyser.fftSize = 512
          analyser.smoothingTimeConstant = 0.3
          analyser.minDecibels = -90
          analyser.maxDecibels = -10
          
          const source = audioContext.createMediaStreamSource(stream)
          source.connect(analyser)
          analyserRef.current = analyser
          
          // Verify stream is active
          const audioTracks = stream.getAudioTracks()
          console.log('Analyser set up for audio level monitoring', {
            audioContextState: audioContext.state,
            trackCount: audioTracks.length,
            trackEnabled: audioTracks[0]?.enabled,
            trackReadyState: audioTracks[0]?.readyState
          })
          
          // Signal that analyser is ready
          setAnalyserReady(true)
          
          const audioRecorder = new Recorder(handleAudioData)
          await audioRecorder.start(stream)
          recorderRef.current = audioRecorder
        } catch (error) {
          console.error('Error accessing microphone:', error)
          alert('Error accessing the microphone. Please check your settings and try again.')
        }
      }

      const handleMessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          // Handle response.audio.delta messages
          if (data?.type === 'response.audio.delta') {
            setIsSpeaking(true)
            //console.log('***Received message:', data)
            // Decode base64 audio data
            const binary = atob(data.delta)
            const bytes = Uint8Array.from(binary, c => c.charCodeAt(0))
            const pcmData = new Int16Array(bytes.buffer)

            // Play audio through AudioWorklet
            audioPlayer.play(pcmData)
          } else if (data?.type === 'response.audio.done') {
            setIsSpeaking(false)
            audioPlayer.stop()
          } else if (data?.type === 'response.done') {
            setIsSpeaking(false)
            audioPlayer.stop()
          } else if (data?.type === 'session.update') {
            console.log('Session updated:', data)
          } else if (data?.type === 'response.audio_transcript.done') {
            console.log('Transcript:', data.transcript)
          } else if (data?.type === 'transcript') {
            console.log('Received message:', data)
            if (data.transcript=="{ \"interrupted\" : true }"){
              audioPlayer.stop()
              audioBufferRef.current = new Uint8Array()
              setIsSpeaking(false)
            }
          } else if (data?.type === 'conversation.item.input_audio_transcription.completed') {
            console.log('Input transcription:', data.transcript)
          } else if (data?.type === 'error') {
            console.error('WebSocket error:', data.error)
            setIsSpeaking(false)
          } else {
            console.log('Received message:', data)
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      const handleError = (error) => {
        console.error('WebSocket error:', error)
        setIsConnected(false)
        setIsSpeaking(false)
        setConversationActive(false)
        
        // Cleanup resources
        if (recorderRef.current) {
          recorderRef.current.stop()
          recorderRef.current = null
        }

        if (playerRef.current) {
          playerRef.current.stop()
        }

        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current)
          animationFrameRef.current = null
        }

        if (analyserContextRef.current) {
          analyserContextRef.current.close()
          analyserContextRef.current = null
        }

        analyserRef.current = null
        mediaStreamRef.current = null
        setAnalyserReady(false)
        audioBufferRef.current = new Uint8Array()
      }

      const handleClose = () => {
        console.log('WebSocket disconnected')
        setIsConnected(false)
        setIsSpeaking(false)
        setConversationActive(false)
        wsRef.current = null

        // Stop recorder
        if (recorderRef.current) {
          recorderRef.current.stop()
          recorderRef.current = null
        }

        // Stop player
        if (playerRef.current) {
          playerRef.current.stop()
        }

        // Cleanup audio level monitoring
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current)
          animationFrameRef.current = null
        }

        if (analyserContextRef.current) {
          analyserContextRef.current.close()
          analyserContextRef.current = null
        }

        analyserRef.current = null
        mediaStreamRef.current = null
        setAnalyserReady(false)

        // Clear buffer
        audioBufferRef.current = new Uint8Array()
      }

      ws.addEventListener('open', handleOpen)
      ws.addEventListener('message', handleMessage)
      ws.addEventListener('error', handleError)
      ws.addEventListener('close', handleClose)

      // Handle case where WebSocket is already open
      if (ws.readyState === WebSocket.OPEN) {
        handleOpen()
      }
    } catch (error) {
      console.error('Failed to connect WebSocket:', error)
      setIsConnected(false)
      if (wsRef.current) {
        wsRef.current = null
      }
    }
  }

  const startConversation = () => {
    if (!isConnected) {
      connectWebSocket()
    }
  }

  const endConversation = () => {
    if (wsRef.current) {
      wsRef.current.close()
      setIsConnected(false)
      setIsSpeaking(false)
      setConversationActive(false)
      wsRef.current = null
    }

    // Stop recorder
    if (recorderRef.current) {
      recorderRef.current.stop()
      recorderRef.current = null
    }

    // Stop and close player
    if (playerRef.current) {
      playerRef.current.stop()
      playerRef.current.close()
      playerRef.current = null
    }

    // Cleanup audio level monitoring
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }

    if (analyserContextRef.current) {
      analyserContextRef.current.close()
      analyserContextRef.current = null
    }

    analyserRef.current = null
    mediaStreamRef.current = null
    setAnalyserReady(false)

    // Clear buffer
    audioBufferRef.current = new Uint8Array()
  }

  return (
    <div className="app">
      <div className={`container ${isConnected ? 'split-layout' : ''}`}>
        {/* Top half - Speaking indicator */}
        {isConnected && (
          <div className="top-half">
            {/* Pulsing image when agent is speaking */}
            {isSpeaking && (
              <div className="speaking-indicator">
                <div className="pulse-ring"></div>
                <div className="pulse-ring pulse-ring-2"></div>
                <div className="pulse-ring pulse-ring-3"></div>
                <div className="center-icon">
                  <svg
                    width="80"
                    height="80"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"
                      fill="currentColor"
                    />
                  </svg>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Bottom half - Main content area */}
        <div className={`content ${isConnected ? 'bottom-half' : ''}`}>
          {/* API Key Input */}
          {showApiKeyInput && (
            <form className="api-key-form" onSubmit={handleApiKeySubmit}>
              <label htmlFor="api-key-input" className="api-key-label">
                Key
              </label>
              <input
                id="api-key-input"
                type="password"
                className="api-key-input"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your key"
                required
                autoFocus
              />
              <button type="submit" className="api-key-submit-button">
                Save Key
              </button>
            </form>
          )}

          {/* Change API Key Button (shown when API key is set) */}
          {!showApiKeyInput && !conversationActive && (
            <div className="api-key-actions">
              <button
                className="change-api-key-button"
                onClick={handleApiKeyChange}
                type="button"
              >
                Change Key
              </button>
              <a
                className="delete-key-link"
                href="#"
                onClick={(e) => {
                  e.preventDefault()
                  handleDeleteKey()
                }}
              >
                Delete key
              </a>
            </div>
          )}

          {/* Provider selection dropdown - visible when disconnected and URL includes /scuti */}
          {!isConnected && window.location.pathname.includes('/uy-scuti-bd-12-5055') && (
            <div className="provider-selector">
              <label htmlFor="provider-select" className="provider-label">
                Provider
              </label>
              <select
                id="provider-select"
                className="provider-select"
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
                disabled={isConnected || showApiKeyInput}
              >
                <option value="gpt-realtime">GPT-Realtime (Speech-to-Speech)</option>
                <option value="assemblyai">AssemblyAI (Speech-to-Speech)</option>
                <option value="gemini-flash">Gemini Flash (Speech-to-Speech)</option>
                <option value="novasonic">Nova Sonic (Speech-to-Speech)</option>
              </select>
            </div>
          )}

          <div className="warning-text"><b>Do not use any real PII</b> when interacting with the demo. Models in use maybe on free/in-trial and data maybe used for training.</div>

          {!conversationActive ? (
            <button
              className="start-button"
              onClick={startConversation}
              disabled={isConnected || showApiKeyInput}
            >
              {isConnected ? 'Connecting...' : 'Start Voice Conversation'}
            </button>
          ) : (
            <div className="conversation-controls">
              <button
                className="control-button end-button"
                onClick={endConversation}
                disabled={!isConnected}
              >
                End Conversation
              </button>
            </div>
          )}

          {/* Connection status indicator */}
          <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
            <span className="status-dot"></span>
            <span className="status-text">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          {/* Audio input level meter */}
          {conversationActive && (
            <div className="audio-level-meter">
              <div className="audio-level-label">Input Level</div>
              <div className="audio-level-bar-container">
                <div 
                  className="audio-level-bar" 
                  style={{ width: `${audioLevel}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
