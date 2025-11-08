import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [isInitialized, setIsInitialized] = useState(false)
  const [urlInputs, setUrlInputs] = useState(['']) // Array of URL inputs
  const [isInitializing, setIsInitializing] = useState(false)
  const [initError, setInitError] = useState('')
  const [loadedUrls, setLoadedUrls] = useState([])
  const [showUrlManager, setShowUrlManager] = useState(false)
  const [newUrlInput, setNewUrlInput] = useState('')
  const [isAddingUrl, setIsAddingUrl] = useState(false)
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I'm your Agno chatbot. I can answer questions based on the knowledge base. How can I help you today?",
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)
  
  // Voice support state
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const recognitionRef = useRef(null)
  const synthRef = useRef(null)
  const finalTranscriptRef = useRef('')
  const speakingTimeoutRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Fetch loaded URLs when component mounts or when initialized
  useEffect(() => {
    if (isInitialized) {
      fetchLoadedUrls()
    }
  }, [isInitialized])

  // Initialize speech recognition and synthesis
  useEffect(() => {
    // Check for browser support
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
      recognitionRef.current = new SpeechRecognition()
      recognitionRef.current.continuous = true  // Keep listening until manually stopped
      recognitionRef.current.interimResults = true  // Get interim results while speaking
      recognitionRef.current.lang = 'en-US'

      recognitionRef.current.onstart = () => {
        setIsListening(true)
        finalTranscriptRef.current = ''
      }

      recognitionRef.current.onresult = (event) => {
        // Process all results
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript
          if (event.results[i].isFinal) {
            finalTranscriptRef.current += transcript + ' '
          }
        }
      }

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error)
        setIsListening(false)
        finalTranscriptRef.current = ''
        if (event.error === 'not-allowed') {
          alert('Microphone permission denied. Please allow microphone access.')
        } else if (event.error === 'network') {
          alert('Network error. Please check your connection.')
        }
      }

      recognitionRef.current.onend = () => {
        setIsListening(false)
      }
    }

    // Initialize speech synthesis
    if ('speechSynthesis' in window) {
      synthRef.current = window.speechSynthesis
    }

    // Cleanup on unmount
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
      if (synthRef.current) {
        synthRef.current.cancel()
      }
      if (speakingTimeoutRef.current) {
        clearTimeout(speakingTimeoutRef.current)
        speakingTimeoutRef.current = null
      }
      setIsSpeaking(false)
    }
  }, [])

  const fetchLoadedUrls = async () => {
    try {
      const response = await axios.get(`${API_URL}/loaded-urls`)
      setLoadedUrls(response.data.urls || [])
    } catch (error) {
      console.error('Error fetching loaded URLs:', error)
    }
  }

  const handleUrlInputChange = (index, value) => {
    const newInputs = [...urlInputs]
    newInputs[index] = value
    setUrlInputs(newInputs)
  }

  const addUrlInput = () => {
    setUrlInputs([...urlInputs, ''])
  }

  const removeUrlInput = (index) => {
    if (urlInputs.length > 1) {
      const newInputs = urlInputs.filter((_, i) => i !== index)
      setUrlInputs(newInputs)
    }
  }

  const handleInitialize = async (e) => {
    e.preventDefault()
    
    // Filter out empty URLs
    const urlsToLoad = urlInputs.map(url => url.trim()).filter(url => url.length > 0)
    
    if (urlsToLoad.length === 0) {
      setInitError('Please enter at least one URL')
      return
    }

    if (isInitializing) return

    setIsInitializing(true)
    setInitError('')

    try {
      const loadedUrlsList = []
      const errors = []

      // Load each URL sequentially
      for (const url of urlsToLoad) {
        try {
          const response = await axios.post(`${API_URL}/initialize`, {
            url: url,
          })

          if (response.data.success) {
            loadedUrlsList.push(...(response.data.loaded_urls || [url]))
          }
        } catch (error) {
          errors.push(`${url}: ${error.response?.data?.detail || error.message}`)
        }
      }

      if (loadedUrlsList.length > 0) {
        setIsInitialized(true)
        setLoadedUrls([...new Set(loadedUrlsList)]) // Remove duplicates
        setUrlInputs([''])
        
        const urlsText = loadedUrlsList.length === 1 
          ? loadedUrlsList[0]
          : `${loadedUrlsList.length} URLs`
        
        setMessages([
          {
            role: 'assistant',
            content: `Hello! I'm your Agno chatbot. I've loaded the knowledge base from ${urlsText}. How can I help you today?`,
          },
        ])

        if (errors.length > 0) {
          setInitError(`Some URLs failed to load:\n${errors.join('\n')}`)
        }
      } else {
        setInitError(`Failed to load any URLs:\n${errors.join('\n')}`)
      }
    } catch (error) {
      console.error('Error initializing:', error)
      setInitError(error.response?.data?.detail || error.message || 'Failed to initialize knowledge base')
    } finally {
      setIsInitializing(false)
    }
  }

  const startListening = () => {
    if (!recognitionRef.current) {
      alert('Speech recognition is not supported in your browser.')
      return
    }

    // Start recording
    finalTranscriptRef.current = ''
    recognitionRef.current.start()
    // onstart handler will set isListening to true
  }

  const handleTranscribeAndPaste = () => {
    // Stop recording first and reset state immediately
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
    }
    
    // Reset speaking state in case it was stuck
    setIsSpeaking(false)
    if (speakingTimeoutRef.current) {
      clearTimeout(speakingTimeoutRef.current)
      speakingTimeoutRef.current = null
    }
    
    // Wait a moment for final transcription, then paste
    setTimeout(() => {
      const transcribedText = finalTranscriptRef.current.trim()
      if (transcribedText) {
        setInput(transcribedText)
      }
      finalTranscriptRef.current = ''
    }, 300)
  }

  const handleTranscribeAndSend = async () => {
    // Stop recording first and reset state immediately
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
    }
    
    // Reset speaking state in case it was stuck
    setIsSpeaking(false)
    if (speakingTimeoutRef.current) {
      clearTimeout(speakingTimeoutRef.current)
      speakingTimeoutRef.current = null
    }
    
    // Wait a moment for final transcription, then send
    setTimeout(async () => {
      const userMessage = finalTranscriptRef.current.trim()
      finalTranscriptRef.current = ''
      
      if (!userMessage) {
        return
      }

      setInput('')
      setIsLoading(true)

      // Build conversation history
      const historyToSend = messages
        .filter((msg) => msg.role !== 'assistant' || msg.content !== "Hello! I'm your Agno chatbot. I can answer questions based on the knowledge base. How can I help you today?")
        .map((msg) => ({
          role: msg.role,
          content: msg.content,
        }))

      // Add user message to UI immediately
      setMessages((prev) => [...prev, { role: 'user', content: userMessage }])

      try {
        const response = await axios.post(`${API_URL}/chat`, {
          message: userMessage,
          history: historyToSend,
        })

        // Add assistant response
        const assistantMessage = response.data.response
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: assistantMessage },
        ])

        // Text-to-speech disabled - uncomment the line below to enable
        // speakText(assistantMessage)
      } catch (error) {
        console.error('Error:', error)
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `Sorry, I encountered an error: ${error.response?.data?.detail || error.message}`,
          },
        ])
      } finally {
        setIsLoading(false)
      }
    }, 300)
  }

  const speakText = (text) => {
    if (!synthRef.current) return

    // Cancel any ongoing speech and reset state
    synthRef.current.cancel()
    setIsSpeaking(false)
    
    // Clear any existing timeout
    if (speakingTimeoutRef.current) {
      clearTimeout(speakingTimeoutRef.current)
      speakingTimeoutRef.current = null
    }

    // Strip markdown formatting for better speech
    let cleanText = text
      .replace(/#{1,6}\s+/g, '') // Remove headers
      .replace(/\*\*(.*?)\*\*/g, '$1') // Remove bold
      .replace(/\*(.*?)\*/g, '$1') // Remove italic
      .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1') // Remove links, keep text
      .replace(/`([^`]+)`/g, '$1') // Remove inline code
      .replace(/```[\s\S]*?```/g, '') // Remove code blocks
      .replace(/\n+/g, '. ') // Replace newlines with periods
      .trim()

    // Limit text length to avoid very long speech
    if (cleanText.length > 500) {
      cleanText = cleanText.substring(0, 500) + '...'
    }

    if (!cleanText) return

    const utterance = new SpeechSynthesisUtterance(cleanText)
    utterance.rate = 1.0
    utterance.pitch = 1.0
    utterance.volume = 1.0

    // Calculate approximate speech duration (characters per second)
    const estimatedDuration = (cleanText.length / 10) * 1000 // Rough estimate: 10 chars per second
    const timeoutDuration = Math.max(estimatedDuration + 2000, 6000) // Add 2 second buffer, minimum 6 seconds

    utterance.onstart = () => {
      setIsSpeaking(true)
      
      // Clear any existing timeout
      if (speakingTimeoutRef.current) {
        clearTimeout(speakingTimeoutRef.current)
      }
      
      // Set fallback timeout to ensure state resets even if onend doesn't fire
      speakingTimeoutRef.current = setTimeout(() => {
        setIsSpeaking(false)
        speakingTimeoutRef.current = null
      }, timeoutDuration)
    }

    utterance.onend = () => {
      setIsSpeaking(false)
      if (speakingTimeoutRef.current) {
        clearTimeout(speakingTimeoutRef.current)
        speakingTimeoutRef.current = null
      }
    }

    utterance.onerror = (event) => {
      console.error('Speech synthesis error:', event)
      setIsSpeaking(false)
      if (speakingTimeoutRef.current) {
        clearTimeout(speakingTimeoutRef.current)
        speakingTimeoutRef.current = null
      }
    }

    // Use a small delay to ensure state is reset before starting new speech
    setTimeout(() => {
      synthRef.current.speak(utterance)
    }, 100)
  }

  const stopSpeaking = () => {
    if (synthRef.current) {
      synthRef.current.cancel()
    }
    // Always reset the state
    setIsSpeaking(false)
    // Clear timeout if exists
    if (speakingTimeoutRef.current) {
      clearTimeout(speakingTimeoutRef.current)
      speakingTimeoutRef.current = null
    }
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setIsLoading(true)

    // Build conversation history from current messages (before adding new user message)
    // Exclude the initial greeting message from history
    const historyToSend = messages
      .filter((msg) => msg.role !== 'assistant' || msg.content !== "Hello! I'm your Agno chatbot. I can answer questions based on the knowledge base. How can I help you today?")
      .map((msg) => ({
        role: msg.role,
        content: msg.content,
      }))

    // Add user message to UI immediately
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])

    try {

      const response = await axios.post(`${API_URL}/chat`, {
        message: userMessage,
        history: historyToSend,
      })

      // Add assistant response
      const assistantMessage = response.data.response
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: assistantMessage },
      ])

      // Text-to-speech disabled - uncomment the line below to enable
      // speakText(assistantMessage)
    } catch (error) {
      console.error('Error:', error)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Sorry, I encountered an error: ${error.response?.data?.detail || error.message}`,
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSkip = () => {
    setIsInitialized(true)
    setMessages([
      {
        role: 'assistant',
        content: "Hello! I'm your Agno chatbot. You can ask me questions, or load a knowledge base from a URL to chat about specific content. How can I help you today?",
      },
    ])
  }

  const handleAddUrl = async (e) => {
    e.preventDefault()
    if (!newUrlInput.trim() || isAddingUrl) return

    const url = newUrlInput.trim()
    setIsAddingUrl(true)
    setInitError('')

    try {
      const response = await axios.post(`${API_URL}/initialize`, {
        url: url,
      })

      if (response.data.success) {
        setLoadedUrls(response.data.loaded_urls || [])
        setNewUrlInput('')
        setShowUrlManager(false)
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `✓ Added knowledge base from ${url}. You can now ask questions about this content.`,
          },
        ])
      }
    } catch (error) {
      console.error('Error adding URL:', error)
      setInitError(error.response?.data?.detail || error.message || 'Failed to add URL')
    } finally {
      setIsAddingUrl(false)
    }
  }

  const handleRemoveUrl = async (url) => {
    if (!confirm(`Remove knowledge base from ${url}?`)) return

    try {
      const response = await axios.post(`${API_URL}/remove-url`, { url })
      if (response.data.success) {
        setLoadedUrls(response.data.remaining_urls || [])
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `✓ Removed knowledge base from ${url}.`,
          },
        ])
      }
    } catch (error) {
      console.error('Error removing URL:', error)
      alert(error.response?.data?.detail || 'Failed to remove URL')
    }
  }

  const handleClearAll = async () => {
    if (!confirm('Clear all knowledge base content? This cannot be undone.')) return

    try {
      const response = await axios.post(`${API_URL}/clear-knowledge-base`)
      if (response.data.success) {
        setLoadedUrls([])
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: '✓ All knowledge base content has been cleared.',
          },
        ])
      }
    } catch (error) {
      console.error('Error clearing knowledge base:', error)
      alert(error.response?.data?.detail || 'Failed to clear knowledge base')
    }
  }

  // Show URL input screen if not initialized
  if (!isInitialized) {
    return (
      <div className="chatbot-container">
        <div className="chatbot-header">
          <h1>🤖 Agno Chatbot</h1>
          <p>Powered by Agno AI with Knowledge Base</p>
        </div>

        <div className="url-input-container">
          <div className="url-input-content">
            <h2>Enter Website URL(s) (Optional)</h2>
            <p>Optionally paste one or more URLs to load a knowledge base and chat about that website's content. You can also skip this step and chat directly.</p>
            
            <form className="url-input-form" onSubmit={handleInitialize}>
              <div className="url-inputs-list">
                {urlInputs.map((url, index) => (
                  <div key={index} className="url-input-row">
                    <input
                      type="url"
                      value={url}
                      onChange={(e) => handleUrlInputChange(index, e.target.value)}
                      placeholder={`https://example.com (optional)`}
                      disabled={isInitializing}
                      autoFocus={index === 0}
                    />
                    {urlInputs.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeUrlInput(index)}
                        className="remove-input-btn"
                        disabled={isInitializing}
                        title="Remove this URL"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
              </div>
              
              <button
                type="button"
                onClick={addUrlInput}
                className="add-url-input-btn"
                disabled={isInitializing}
              >
                + Add Another URL
              </button>

              <div className="url-input-buttons">
                <button 
                  type="submit" 
                  disabled={isInitializing || urlInputs.every(url => !url.trim())}
                >
                  {isInitializing ? 'Loading...' : `Load Knowledge Base${urlInputs.filter(url => url.trim()).length > 1 ? 's' : ''}`}
                </button>
                <button 
                  type="button" 
                  onClick={handleSkip}
                  disabled={isInitializing}
                  className="skip-button"
                >
                  Continue Without URL
                </button>
              </div>
            </form>

            {initError && (
              <div className="error-message">
                {initError}
              </div>
            )}

            {isInitializing && (
              <div className="loading-message">
                <p>Loading content from the website. This may take a moment...</p>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // Show chat interface after initialization
  return (
    <div className="chatbot-container">
      <div className="chatbot-header">
        <div className="header-content">
          <div>
            <h1>🤖 Agno Chatbot</h1>
            <p>Powered by Agno AI with Knowledge Base</p>
          </div>
          <button 
            className="url-manager-toggle"
            onClick={() => setShowUrlManager(!showUrlManager)}
            title="Manage Knowledge Base URLs"
          >
            {showUrlManager ? '✕' : '⚙️'}
          </button>
        </div>
        {showUrlManager && (
          <div className="url-manager">
            <h3>Knowledge Base URLs ({loadedUrls.length})</h3>
            {loadedUrls.length > 0 ? (
              <>
                <div className="loaded-urls-list">
                  {loadedUrls.map((url, idx) => (
                    <div key={idx} className="url-item">
                      <span className="url-text" title={url}>{url}</span>
                      <button 
                        className="remove-url-btn"
                        onClick={() => handleRemoveUrl(url)}
                        title="Remove this URL"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
                <button className="clear-all-btn" onClick={handleClearAll}>
                  Clear All
                </button>
              </>
            ) : (
              <p className="no-urls">No URLs loaded</p>
            )}
            <form className="add-url-form" onSubmit={handleAddUrl}>
              <input
                type="url"
                value={newUrlInput}
                onChange={(e) => setNewUrlInput(e.target.value)}
                placeholder="Add new URL..."
                disabled={isAddingUrl}
              />
              <button type="submit" disabled={isAddingUrl || !newUrlInput.trim()}>
                {isAddingUrl ? 'Adding...' : 'Add URL'}
              </button>
            </form>
            {initError && (
              <div className="error-message-small">
                {initError}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="chatbot-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <div className="message-content">
              {msg.role === 'assistant' ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message assistant">
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form className="chatbot-input" onSubmit={handleSend}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isListening ? "Listening..." : "Type your message or click 🎙️ to speak..."}
          disabled={isLoading || isListening}
          autoFocus
        />
        {!isListening ? (
          <button
            type="button"
            className="voice-btn-inline"
            onClick={startListening}
            disabled={isLoading}
            title="Start voice recording"
          >
            🎙️
          </button>
        ) : (
          <>
            <button
              type="button"
              className="voice-btn-inline paste-icon-btn"
              onClick={handleTranscribeAndPaste}
              disabled={isLoading}
              title="Transcribe and paste in input"
            >
              📋
            </button>
            <button
              type="button"
              className="voice-btn-inline send-icon-btn"
              onClick={handleTranscribeAndSend}
              disabled={isLoading}
              title="Transcribe and send automatically"
            >
              ➤
            </button>
          </>
        )}
        <button type="submit" disabled={isLoading || !input.trim() || isListening}>
          {isLoading ? '⏳' : '➤'}
        </button>
      </form>
    </div>
  )
}

export default App

