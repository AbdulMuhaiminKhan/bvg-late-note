// Copy or share the "I'm running late" message on the note page.
// Loaded as a file because the Content-Security-Policy blocks inline scripts.
(function () {
  var box = document.getElementById("late-message");
  var copyBtn = document.getElementById("copy-message");
  var shareBtn = document.getElementById("share-message");
  var status = document.getElementById("send-status");
  if (!box || !copyBtn) return;

  function say(text) {
    status.textContent = text;
    setTimeout(function () { status.textContent = ""; }, 4000);
  }

  copyBtn.addEventListener("click", function () {
    var text = box.value;
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(
        function () { say("Copied. Paste it into any chat."); },
        function () { box.select(); say("Select the text and copy it with your keyboard."); }
      );
    } else {
      box.select();
      try { document.execCommand("copy"); say("Copied. Paste it into any chat."); }
      catch (e) { say("Select the text and copy it with your keyboard."); }
    }
  });

  if (navigator.share && shareBtn) {
    shareBtn.hidden = false;
    shareBtn.addEventListener("click", function () {
      navigator.share({ text: box.value }).catch(function () {});
    });
  }
})();
