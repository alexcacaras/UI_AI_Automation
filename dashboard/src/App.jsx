import { useEffect, useState } from 'react'
import './App.css'

function App() {
  const [url, setUrl] = useState(
    ''
  )

  const [operation, setOperation] = useState('record')

  // Record state
  const [name, setName] = useState('')
  const [goal, setGoal] = useState('')
  const [recordMode, setRecordMode] = useState('overlay')

  // Playback state
  const [recordings, setRecordings] = useState([])
  const [selectedRecording, setSelectedRecording] = useState('')
  const [playbackResult, setPlaybackResult] = useState(null)

  // Suite state
  const [suiteSelection, setSuiteSelection] = useState([])
  const [suiteResults, setSuiteResults] = useState([])

  // Global state
  const [status, setStatus] = useState('Engine ready')
  const [browserLaunched, setBrowserLaunched] = useState(false)
  const [busy, setBusy] = useState(false)

  const [logs, setLogs] = useState([])

  // =========================================================
  // INITIAL LOAD + SSE
  // =========================================================

  useEffect(() => {
    loadRecordings()
    loadStatus()

    const events = new EventSource('/api/stream')

    events.onmessage = (event) => {
      const data = JSON.parse(event.data)

      // Normal log
      if (data.type === 'log') {
        setLogs((old) => [...old, data.text])
      }

      // Browser opened
      if (data.type === 'browser_opened') {
        setBrowserLaunched(true)
        setStatus('Browser open — log into Oracle')
      }

      // Recording started
      if (data.type === 'recording_started') {
        setBusy(true)
        setStatus(`Recording: ${data.name}`)
      }

      // Recording finished
      if (data.type === 'recording_finished') {
        setBusy(false)

        loadRecordings()

        if (data.signal === 'new') {
          setStatus(
            `Saved: ${data.name} — ready for new recording`
          )

          setName('')
          setGoal('')
        } else {
          setStatus(
            `Saved: ${data.name} — finishing session`
          )

          setName('')
          setGoal('')
        }
      }

      // Recording error
      if (data.type === 'recording_error') {
        setBusy(false)
        setStatus(`Recording error: ${data.message}`)
      }

      // Playback started
      if (data.type === 'playback_started') {
        setBusy(true)
        setPlaybackResult(null)
        setStatus(`Playing: ${data.name}`)
      }

      // Playback complete
      if (data.type === 'playback_finished') {
        setBusy(false)

        setPlaybackResult({
          name: data.name,
          result: data.result,
          message: data.message || '',
        })

        setStatus(
          `Playback ${data.result}: ${data.name}`
        )
      }

      // Suite started
      if (data.type === 'suite_started') {
        setBusy(true)
        setSuiteResults([])

        setStatus(
          `Suite running: ${data.tests.length} tests`
        )
      }

      // Suite test started
      if (data.type === 'suite_test_started') {
        setStatus(
          `Running ${data.position}/${data.total}: ${data.name}`
        )
      }

      // Suite test finished
      if (data.type === 'suite_test_finished') {
        setSuiteResults((old) => [
          ...old,
          {
            name: data.name,
            result: data.result,
          },
        ])
      }

      // Suite finished
      if (data.type === 'suite_finished') {
        setBusy(false)

        setStatus(
          `Suite complete: ${data.passed} passed, ${data.failed} failed`
        )
      }

      // Browser closed
      if (data.type === 'browser_closed') {
        setBrowserLaunched(false)
        setBusy(false)

        setStatus('Engine ready')
      }

      // Worker error
      if (data.type === 'worker_error') {
        setBrowserLaunched(false)
        setBusy(false)

        setStatus(`Worker error: ${data.message}`)
      }
    }

    events.onerror = () => {
      // EventSource reconnects automatically.
    }

    return () => {
      events.close()
    }
  }, [])

  // =========================================================
  // STATUS
  // =========================================================

  async function loadStatus() {
    try {
      const response = await fetch('/api/status')
      const data = await response.json()

      setBrowserLaunched(Boolean(data.browser_open))
      setBusy(Boolean(data.busy))

      if (data.busy) {
        setStatus('Automation running')
      } else if (data.browser_open) {
        setStatus('Browser open')
      }
    } catch {
      // Flask may still be starting.
    }
  }

  // =========================================================
  // RECORDINGS LIST
  // =========================================================

  async function loadRecordings() {
    try {
      const response = await fetch('/api/recordings')
      const data = await response.json()

      const items = data.recordings || []

      setRecordings(items)

      if (items.length > 0) {
        setSelectedRecording((current) => {
          const stillExists = items.some(
            (item) => item.name === current
          )

          return stillExists
            ? current
            : items[0].name
        })

        setSuiteSelection((current) =>
          current.filter((selected) =>
            items.some(
              (recording) =>
                recording.name === selected
            )
          )
        )
      } else {
        setSelectedRecording('')
        setSuiteSelection([])
      }
    } catch (error) {
      console.error(
        'Could not load recordings:',
        error
      )
    }
  }

  // =========================================================
  // FILES & REPORTS
  // =========================================================

  async function openRecordingsFolder() {
    try {
      const response = await fetch(
        '/api/open-recordings',
        {
          method: 'POST',
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.message ||
            'Could not open recordings folder'
        )
      }

      setStatus('Opened recordings folder')
    } catch (error) {
      setStatus(`Error: ${error.message}`)
    }
  }

  async function openDocsFolder() {
    try {
      const response = await fetch(
        '/api/open-docs',
        {
          method: 'POST',
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.message ||
            'Could not open reports folder'
        )
      }

      setStatus('Opened reports & screenshots')
    } catch (error) {
      setStatus(`Error: ${error.message}`)
    }
  }

  // =========================================================
  // LAUNCH BROWSER
  // =========================================================

  async function launchBrowser() {
    try {
      setStatus('Launching browser...')

      const response = await fetch('/api/launch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.message || 'Launch failed'
        )
      }

      setBrowserLaunched(true)
      setStatus('Browser opening...')
    } catch (error) {
      setStatus(`Error: ${error.message}`)
    }
  }

  // =========================================================
  // START RECORDING
  // =========================================================

  async function startRecording(overwrite = false) {
    if (!name.trim()) {
      setStatus('Enter a recording name')
      return
    }

    if (!goal.trim()) {
      setStatus('Enter a goal')
      return
    }

    try {
      setStatus(`Starting ${name}...`)

      const response = await fetch('/api/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          mode: recordMode,
          name,
          goal,
          overwrite,
        }),
      })

      const data = await response.json()

      // Existing recording — ask before overwrite.
      if (
        response.status === 409 &&
        data.status === 'exists'
      ) {
        const confirmed = window.confirm(
          `Recording "${name}" already exists.\n\nOverwrite it?`
        )

        if (confirmed) {
          return startRecording(true)
        }

        setStatus('Overwrite cancelled')
        return
      }

      if (!response.ok) {
        throw new Error(
          data.message ||
            'Could not start recording'
        )
      }

      setBusy(true)
      setStatus(`Recording: ${name}`)
    } catch (error) {
      setBusy(false)
      setStatus(`Error: ${error.message}`)
    }
  }

  // =========================================================
  // PLAYBACK
  // =========================================================

  async function startPlayback() {
    if (!selectedRecording) {
      setStatus('Choose a recording first')
      return
    }

    try {
      setBusy(true)
      setPlaybackResult(null)

      setStatus(
        `Starting playback: ${selectedRecording}`
      )

      const response = await fetch('/api/playback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: selectedRecording,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.message ||
            'Could not start playback'
        )
      }
    } catch (error) {
      setBusy(false)
      setStatus(`Error: ${error.message}`)
    }
  }

  // =========================================================
  // RUN SUITE
  // =========================================================

  async function startSuite() {
    if (suiteSelection.length === 0) {
      setStatus('Choose at least one recording')
      return
    }

    try {
      setBusy(true)
      setSuiteResults([])

      setStatus(
        `Starting suite: ${suiteSelection.length} tests`
      )

      const response = await fetch('/api/run-suite', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tests: suiteSelection,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.message ||
            'Could not start suite'
        )
      }
    } catch (error) {
      setBusy(false)
      setStatus(`Error: ${error.message}`)
    }
  }

  // =========================================================
  // SUITE SELECTION
  // =========================================================

  function toggleSuiteRecording(recordingName) {
    setSuiteSelection((current) => {
      if (current.includes(recordingName)) {
        return current.filter(
          (item) => item !== recordingName
        )
      }

      return [
        ...current,
        recordingName,
      ]
    })
  }

  function moveSuiteItem(index, direction) {
    setSuiteSelection((current) => {
      const target = index + direction

      if (
        target < 0 ||
        target >= current.length
      ) {
        return current
      }

      const copy = [...current]

      const [item] = copy.splice(index, 1)

      copy.splice(target, 0, item)

      return copy
    })
  }

  // =========================================================
  // CLOSE SESSION
  // =========================================================

  async function closeBrowser() {
    try {
      setStatus(
        'Closing browser session...'
      )

      const response = await fetch('/api/close', {
        method: 'POST',
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data.message ||
            'Could not close browser'
        )
      }
    } catch (error) {
      setStatus(`Error: ${error.message}`)
    }
  }

  // =========================================================
  // UI
  // =========================================================

  return (
    <div className="app">
      <header>
        <div>
          <h1>UI Automation</h1>
          <p>
            Local browser automation (AI driving soon)
          </p>
        </div>

        <div className="engine-status">
          <span className="status-dot"></span>
          {status}
        </div>
      </header>

      <main>

        {/* ==================================================
            01 — BROWSER
        ================================================== */}

        <section className="card">
          <div className="card-title">
            <span>01</span>
            Browser Session
          </div>

          <label>Oracle Instance</label>

          <div className="row">
            <input
              value={url}
              onChange={(e) =>
                setUrl(e.target.value)
              }
              placeholder="Oracle URL"
              disabled={browserLaunched}
            />

            <button
              className="primary"
              onClick={launchBrowser}
              disabled={browserLaunched}
            >
              {browserLaunched
                ? 'Browser Open'
                : 'Launch Browser'}
            </button>

            {browserLaunched && !busy && (
              <button
                className="secondary"
                onClick={closeBrowser}
              >
                End Session
              </button>
            )}
          </div>

          {browserLaunched && (
            <p className="hint">
              Log into Oracle in the opened browser,
              then choose an operation below.
            </p>
          )}
        </section>

        {/* ==================================================
            02 — OPERATION
        ================================================== */}

        <section className="card">
          <div className="card-title">
            <span>02</span>
            Operation
          </div>

          <label>
            What do you want to do?
          </label>

          <select
            value={operation}
            onChange={(e) => {
              setOperation(
                e.target.value
              )

              setPlaybackResult(null)
              setSuiteResults([])
            }}
            disabled={busy}
            className="operation-select"
          >
            <option value="record">
              Record
            </option>

            <option value="playback">
              Playback
            </option>

            <option value="suite">
              Run Suite
            </option>
          </select>
        </section>

        {/* ==================================================
            RECORD
        ================================================== */}

        {operation === 'record' && (
          <section className="card">
            <div className="card-title">
              <span>03</span>

              {busy
                ? 'Recording in Progress'
                : 'New Recording'}
            </div>

            <div className="form-grid">

              <div>
                <label>
                  Recording Name
                </label>

                <input
                  value={name}
                  onChange={(e) =>
                    setName(
                      e.target.value
                    )
                  }
                  placeholder="change_assignment"
                  disabled={busy}
                />
              </div>

              <div>
                <label>
                  Record Method
                </label>

                <select
                  value={recordMode}
                  onChange={(e) =>
                    setRecordMode(
                      e.target.value
                    )
                  }
                  disabled={busy}
                >
                  <option value="overlay">
                    Overlay
                  </option>

                  <option value="ai">
                    AI
                  </option>

                  <option value="manual">
                    Manual
                  </option>
                </select>
              </div>

            </div>

            <label>Goal</label>

            <textarea
              value={goal}
              onChange={(e) =>
                setGoal(
                  e.target.value
                )
              }
              placeholder="Describe what this automation should accomplish..."
              rows="4"
              disabled={busy}
            />

            <button
              className="primary start-button"
              onClick={() =>
                startRecording(false)
              }
              disabled={
                !browserLaunched ||
                busy
              }
            >
              {busy
                ? 'Recording Active'
                : 'Start Recording'}
            </button>

            {busy && (
              <p className="hint">
                New Recording saves the current
                recording and keeps Oracle open.
                Finish saves the recording and
                closes the browser session.
              </p>
            )}
          </section>
        )}

        {/* ==================================================
            PLAYBACK
        ================================================== */}

        {operation === 'playback' && (
          <section className="card">
            <div className="card-title">
              <span>03</span>
              Playback
            </div>

            <label>
              Saved Recording
            </label>

            <select
              value={selectedRecording}
              onChange={(e) =>
                setSelectedRecording(
                  e.target.value
                )
              }
              disabled={
                busy ||
                recordings.length === 0
              }
            >
              {recordings.length === 0 ? (
                <option value="">
                  No recordings found
                </option>
              ) : (
                recordings.map(
                  (recording) => (
                    <option
                      key={recording.name}
                      value={recording.name}
                    >
                      {recording.name}
                      {' — '}
                      {recording.steps} steps
                    </option>
                  )
                )
              )}
            </select>

            {selectedRecording && (
              <div className="recording-info">
                {recordings
                  .filter(
                    (recording) =>
                      recording.name ===
                      selectedRecording
                  )
                  .map((recording) => (
                    <div
                      key={recording.name}
                    >
                      <strong>
                        {recording.name}
                      </strong>

                      {recording.goal && (
                        <p>
                          {recording.goal}
                        </p>
                      )}

                      <span>
                        {recording.steps}{' '}
                        recorded steps
                      </span>
                    </div>
                  ))}
              </div>
            )}

            <button
              className="primary start-button"
              onClick={startPlayback}
              disabled={
                !browserLaunched ||
                busy ||
                !selectedRecording
              }
            >
              {busy
                ? 'Playback Running'
                : 'Run Playback'}
            </button>

            {playbackResult && (
              <div
                className={
                  playbackResult.result ===
                  'PASS'
                    ? 'result pass'
                    : 'result fail'
                }
              >
                <strong>
                  {playbackResult.result}
                </strong>

                <span>
                  {playbackResult.name}
                </span>

                {playbackResult.message && (
                  <p>
                    {playbackResult.message}
                  </p>
                )}
              </div>
            )}
          </section>
        )}

        {/* ==================================================
            RUN SUITE
        ================================================== */}

        {operation === 'suite' && (
          <section className="card">
            <div className="card-title">
              <span>03</span>
              Run Suite
            </div>

            <p className="hint">
              Select recordings in the order
              you want them to run.
            </p>

            <div className="suite-list">

              {recordings.length === 0 ? (
                <div className="empty-log">
                  No recordings found.
                </div>
              ) : (
                recordings.map(
                  (recording) => {
                    const selected =
                      suiteSelection.includes(
                        recording.name
                      )

                    const orderIndex =
                      suiteSelection.indexOf(
                        recording.name
                      )

                    return (
                      <div
                        key={recording.name}
                        className="suite-item"
                      >
                        <input
                          type="checkbox"
                          checked={selected}
                          disabled={busy}
                          onChange={() =>
                            toggleSuiteRecording(
                              recording.name
                            )
                          }
                        />

                        <div className="suite-item-info">
                          <strong>
                            {recording.name}
                          </strong>

                          <span>
                            {recording.steps}{' '}
                            steps
                          </span>
                        </div>

                        {selected && (
                          <div className="suite-item-order">
                            <span>
                              #{orderIndex + 1}
                            </span>
                          </div>
                        )}
                      </div>
                    )
                  }
                )
              )}
            </div>

            {suiteSelection.length > 0 && (
              <div className="suite-order">
                <strong>
                  Run Order
                </strong>

                {suiteSelection.map(
                  (test, index) => (
                    <div
                      key={test}
                      className="suite-order-row"
                    >
                      <span>
                        {index + 1}. {test}
                      </span>

                      <div>
                        <button
                          className="order-button"
                          disabled={
                            busy ||
                            index === 0
                          }
                          onClick={() =>
                            moveSuiteItem(
                              index,
                              -1
                            )
                          }
                        >
                          ↑
                        </button>

                        <button
                          className="order-button"
                          disabled={
                            busy ||
                            index ===
                              suiteSelection.length - 1
                          }
                          onClick={() =>
                            moveSuiteItem(
                              index,
                              1
                            )
                          }
                        >
                          ↓
                        </button>
                      </div>
                    </div>
                  )
                )}
              </div>
            )}

            <button
              className="primary start-button"
              onClick={startSuite}
              disabled={
                !browserLaunched ||
                busy ||
                suiteSelection.length === 0
              }
            >
              {busy
                ? 'Suite Running'
                : suiteSelection.length > 0
                  ? `Run ${suiteSelection.length} Tests`
                  : 'Run Suite'}
            </button>

            {suiteResults.length > 0 && (
              <div className="suite-results">
                {suiteResults.map(
                  (item, index) => (
                    <div
                      key={`${item.name}-${index}`}
                      className={
                        item.result === 'PASS'
                          ? 'suite-result pass'
                          : 'suite-result fail'
                      }
                    >
                      <strong>
                        {item.result}
                      </strong>

                      <span>
                        {item.name}
                      </span>
                    </div>
                  )
                )}
              </div>
            )}
          </section>
        )}

        {/* ==================================================
            04 — FILES & REPORTS
        ================================================== */}

        <section className="card">
          <div className="card-title">
            <span>04</span>
            Files & Reports
          </div>

          <p className="hint">
            Access saved recording JSON files and generated
            reports and screenshots directly on this computer.
          </p>

          <div className="file-actions">
            <button
              className="secondary"
              onClick={openRecordingsFolder}
            >
              Open Recordings Folder
            </button>

            <button
              className="secondary"
              onClick={openDocsFolder}
            >
              Open Reports & Screenshots
            </button>
          </div>
        </section>

        {/* ==================================================
            05 — LIVE ACTIVITY
        ================================================== */}

        <section className="card activity">
          <div className="card-title">
            <span>05</span>
            Live Activity
          </div>

          <div className="terminal">
            {logs.length === 0 ? (
              <div className="empty-log">
                Waiting for automation
                activity...
              </div>
            ) : (
              logs.map(
                (line, index) => (
                  <div
                    className="log-line"
                    key={index}
                  >
                    <span className="prompt">
                      &gt;
                    </span>

                    {line}
                  </div>
                )
              )
            )}
          </div>
        </section>

      </main>
    </div>
  )
}

export default App