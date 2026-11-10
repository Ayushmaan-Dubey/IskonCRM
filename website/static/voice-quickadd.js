// Voice quick-add: joins a LiveKit room with the voice agent, plays its audio, and performs
// the save when the agent asks (RPC "save_newcomers") using the volunteer's own login session.
(function () {
  var panel = document.getElementById('voice-quickadd');
  if (!panel || !window.LivekitClient) return;

  var startBtn = document.getElementById('voice-start');
  var stopBtn = document.getElementById('voice-stop');
  var statusEl = document.getElementById('voice-status');
  var resultsEl = document.getElementById('voice-results');
  var room = null;

  function setStatus(text) { statusEl.textContent = text; }

  function showSaved(results) {
    results.forEach(function (r) {
      var li = document.createElement('li');
      li.textContent = r.full_name + ' — ' + r.status + (r.reason ? ' (' + r.reason + ')' : '');
      resultsEl.appendChild(li);
    });
  }

  function reset(message) {
    startBtn.disabled = false;
    stopBtn.classList.add('d-none');
    startBtn.classList.remove('d-none');
    document.querySelectorAll('audio[data-lk]').forEach(function (el) { el.remove(); });
    room = null;
    setStatus(message || 'Ready.');
  }

  async function start() {
    startBtn.disabled = true;
    setStatus('Connecting…');
    try {
      var resp = await fetch(panel.dataset.tokenUrl, { method: 'POST', credentials: 'same-origin' });
      var body = await resp.json();
      if (!resp.ok) throw new Error(body.error || 'Could not start voice quick-add.');

      var LK = window.LivekitClient;
      room = new LK.Room();
      room.on(LK.RoomEvent.TrackSubscribed, function (track) {
        if (track.kind !== 'audio') return;
        var el = track.attach();
        el.dataset.lk = '1';
        document.body.appendChild(el);
      });
      room.on(LK.RoomEvent.TrackUnsubscribed, function (track) {
        track.detach().forEach(function (el) { el.remove(); });
      });
      room.on(LK.RoomEvent.Disconnected, function () { reset('Session ended.'); });

      room.localParticipant.registerRpcMethod('save_newcomers', async function (data) {
        var people = JSON.parse(data.payload).people;
        var saveResp = await fetch(panel.dataset.saveUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ people: people }),
        });
        var saveBody = await saveResp.json();
        if (!saveResp.ok) throw new Error(saveBody.error || 'Save failed.');
        showSaved(saveBody.results);
        return JSON.stringify(saveBody);
      });

      await room.connect(body.url, body.token);
      await room.startAudio();
      await room.localParticipant.setMicrophoneEnabled(true);
      startBtn.classList.add('d-none');
      stopBtn.classList.remove('d-none');
      setStatus('Listening — just start talking.');
    } catch (err) {
      if (room) room.disconnect();
      reset(err && err.name === 'NotAllowedError'
        ? 'Microphone access was blocked. Allow it in the browser and try again.'
        : (err && err.message) || 'Something went wrong.');
    }
  }

  startBtn.addEventListener('click', start);
  stopBtn.addEventListener('click', function () { if (room) room.disconnect(); });
  window.addEventListener('beforeunload', function () { if (room) room.disconnect(); });
})();
