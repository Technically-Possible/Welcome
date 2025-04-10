document.addEventListener("DOMContentLoaded", async () => {
    const gallery = document.getElementById("gallery");
    let allImages = []; // Store all full-size image paths for navigation
    let currentIndex = 0; // Track the current image index

    try {
        const response = await fetch("photography.json"); // Fetch JSON data
        const data = await response.json();
        
        gallery.innerHTML = ""; // Clear loading text

        // ✅ Sort years in descending order (2025 before 2024)
        data.years.sort((a, b) => b.year.localeCompare(a.year)).forEach(year => {
            const yearSection = document.createElement("section");
            yearSection.classList.add("year-section");

            // Create year heading
            const yearTitle = document.createElement("h1");
            yearTitle.textContent = year.year;
            yearSection.appendChild(yearTitle);

            year.events.forEach(event => {
                const eventSection = document.createElement("section");
                eventSection.classList.add("event-section");

                // Create event (location) subheading
                const eventTitle = document.createElement("h2");
                eventTitle.textContent = event.name;  // Location Name (e.g., Liverpool)
                eventSection.appendChild(eventTitle);

                const imageContainer = document.createElement("div");
                imageContainer.classList.add("image-grid");

                // ✅ Sort images before displaying (ensuring correct order)
                event.images.sort((a, b) => a.full.localeCompare(b.full)).forEach((imageObj) => {
                    const imgThumbPath = imageObj.thumb;
                    const imgFullPath = imageObj.full;

                    // ✅ Correctly store the index of this specific image
                    const imgIndex = allImages.length;
                    allImages.push(imgFullPath); // Store full-size image path

                    const imgElement = document.createElement("img");
                    imgElement.src = imgThumbPath; // Load thumbnail first
                    imgElement.dataset.full = imgFullPath; // Store full-size path
                    imgElement.alt = "Gallery Image";
                    imgElement.classList.add("photo-thumb");
                    imgElement.setAttribute("loading", "lazy"); // ✅ Lazy Loading for better performance

                    // ✅ Attach the correct index to each image when clicked
                    imgElement.addEventListener("click", () => openLightbox(imgIndex));

                    imageContainer.appendChild(imgElement);
                });

                eventSection.appendChild(imageContainer);
                yearSection.appendChild(eventSection);
            });

            gallery.appendChild(yearSection);
        });

        // ✅ Add Lightbox HTML (Only once)
        document.body.insertAdjacentHTML("beforeend", `
            <div class="lightbox" id="lightbox">
                <span class="lightbox-close" onclick="closeLightbox()">&times;</span>
                <img id="lightbox-img" src="" alt="Expanded Image">
                <div class="lightbox-arrow left-arrow" onclick="prevImage()">&#10094;</div>
                <div class="lightbox-arrow right-arrow" onclick="nextImage()">&#10095;</div>
            </div>
            
            <!-- Loading throbber -->
            <div class="loading-throbber" id="loading-throbber">
                <div class="spinner"></div>
                <p>Loading image...</p>
            </div>
        `);

    } catch (error) {
        console.error("Error loading photography data", error);
    }

    // ✅ Open Lightbox with Correct Image
    function openLightbox(index) {
        currentIndex = index; // Set current image index
        const fullImageSrc = allImages[currentIndex];
        
        // Show the loading throbber
        document.getElementById("loading-throbber").style.display = "block";
        
        const lightboxImg = document.getElementById("lightbox-img");
        lightboxImg.src = ''; // Clear the previous image to trigger load event

        // Listen for image load event
        lightboxImg.onload = () => {
            // Hide the throbber when image has loaded
            document.getElementById("loading-throbber").style.display = "none";
        };
        
        // Set the new image source to load the new image
        lightboxImg.src = fullImageSrc; // Load full image when clicked
        document.getElementById("lightbox").classList.add("active");
    }

    // ✅ Close Lightbox
    function closeLightbox() {
        document.getElementById("lightbox").classList.remove("active");
    }

    // ✅ Navigate Left (Previous Image)
    function prevImage() {
        currentIndex = (currentIndex - 1 + allImages.length) % allImages.length;
        const fullImageSrc = allImages[currentIndex];

        // Show loading throbber while the new image is being loaded
        document.getElementById("loading-throbber").style.display = "block";

        const lightboxImg = document.getElementById("lightbox-img");
        lightboxImg.src = ''; // Clear the previous image to trigger load event

        // Listen for image load event
        lightboxImg.onload = () => {
            // Hide the throbber when image has loaded
            document.getElementById("loading-throbber").style.display = "none";
        };
        
        lightboxImg.src = fullImageSrc;
    }

    // ✅ Navigate Right (Next Image)
    function nextImage() {
        currentIndex = (currentIndex + 1) % allImages.length;
        const fullImageSrc = allImages[currentIndex];

        // Show loading throbber while the new image is being loaded
        document.getElementById("loading-throbber").style.display = "block";

        const lightboxImg = document.getElementById("lightbox-img");
        lightboxImg.src = ''; // Clear the previous image to trigger load event

        // Listen for image load event
        lightboxImg.onload = () => {
            // Hide the throbber when image has loaded
            document.getElementById("loading-throbber").style.display = "none";
        };
        
        lightboxImg.src = fullImageSrc;
    }

    // ✅ Keyboard Controls for Navigation
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeLightbox();
        if (event.key === "ArrowLeft") prevImage();
        if (event.key === "ArrowRight") nextImage();
    });

    // ✅ Touch Swipe for Mobile Navigation
    let touchStartX = 0;
    let touchEndX = 0;

    document.getElementById("lightbox").addEventListener("touchstart", (event) => {
        touchStartX = event.changedTouches[0].screenX;
    });

    document.getElementById("lightbox").addEventListener("touchend", (event) => {
        touchEndX = event.changedTouches[0].screenX;
        handleSwipe();
    });

    function handleSwipe() {
        if (touchStartX - touchEndX > 50) nextImage();  // Swipe Left
        if (touchEndX - touchStartX > 50) prevImage();  // Swipe Right
    }
});
