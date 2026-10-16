"use strict";

// No video connection is made until the visitor activates this control.
const video = document.querySelector("[data-video-id]");
if (video) {
  const id = video.dataset.videoId.trim();
  if (/^[\w-]{11}$/.test(id)) {
    const button = video.querySelector(".video-play");
    const fallback = video.querySelector(".youtube-fallback");
    const status = video.querySelector("#video-status");
    button.disabled = false;
    video.querySelector(".pill").textContent = "Demo video";
    video.querySelector(".video-pending").hidden = true;
    fallback.href = `https://www.youtube.com/watch?v=${id}`;
    fallback.hidden = false;
    status.textContent = "Play loads YouTube. The written walkthrough is available below.";
    button.addEventListener("click", () => {
      const frame = document.createElement("iframe");
      frame.src = `https://www.youtube-nocookie.com/embed/${id}?autoplay=1`;
      frame.title = "Givlah demo: from listing to recorded handover";
      frame.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
      frame.referrerPolicy = "strict-origin-when-cross-origin";
      frame.allowFullscreen = true;
      video.querySelector(".video-frame").replaceChildren(frame);
      status.textContent = "Video loaded from YouTube. If playback fails, use Watch on YouTube or the written walkthrough.";
      frame.tabIndex = 0;
      frame.focus();
    }, {once: true});
  }
}

// Keep ordinary anchor links fully usable without JavaScript.
if ("IntersectionObserver" in window) {
  const links = [...document.querySelectorAll('.sidebar nav a[href^="#"]')];
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      for (const link of links) {
        if (link.hash === `#${entry.target.id}`) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      }
    }
  }, {rootMargin: "0px 0px -65% 0px", threshold: 0});
  document.querySelectorAll("main > section[id]").forEach(section => observer.observe(section));
}
