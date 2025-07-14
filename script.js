// Animation skip logic
document.addEventListener("DOMContentLoaded", function() {
  const lastVisit = localStorage.getItem("lastVisitDate");
  const now = new Date();
  const today = now.toISOString().split('T')[0];

  if (lastVisit === today) {
    document.body.classList.add("no-animation");
  } else {
    setTimeout(() => {
      localStorage.setItem("lastVisitDate", today);
    }, 10000); // Adjust delay to your animation length
  }
});
// Function to toggle display of full-size image
function toggleFullSizeImageDisplay(imgElement, path) {
  window.open(path, '_blank'); // Open the image in a new tab/window
}

