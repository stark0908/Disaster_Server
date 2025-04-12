document.addEventListener("DOMContentLoaded", function() {

    // Get reference to the status div for SOS form feedback
    const sosStatusDiv = document.getElementById('sosStatus');

    // --- Updated SOS Form Submission ---
    const sosForm = document.getElementById("sosForm");
    if (sosForm) {
        sosForm.addEventListener("submit", function(e) {
            e.preventDefault(); // Prevent default form submission

            // Clear previous status and set loading message
            if (sosStatusDiv) {
                sosStatusDiv.textContent = 'Sending SOS...';
                sosStatusDiv.className = ''; // Reset class
            }

            // Get values from the NEW form fields
            const disasterType = document.getElementById('disasterType').value;
            const latitudeInput = document.getElementById('latitude');
            const longitudeInput = document.getElementById('longitude');
            const details = document.getElementById('details').value;
            const mobileNumber = document.getElementById('mobileNumber').value;

            // --- Validation ---
            let isValid = true;
            let latitude = NaN;
            let longitude = NaN;

            try {
                 latitude = parseFloat(latitudeInput.value);
                 longitude = parseFloat(longitudeInput.value);

                if (isNaN(latitude) || isNaN(longitude)) {
                    throw new Error('Please enter valid numbers for Latitude and Longitude.');
                }
                 if (latitude < -90 || latitude > 90) {
                    throw new Error('Latitude must be between -90 and 90.');
                 }
                 if (longitude < -180 || longitude > 180) {
                     throw new Error('Longitude must be between -180 and 180.');
                 }

            } catch (error) {
                if (sosStatusDiv) {
                    sosStatusDiv.textContent = error.message;
                    sosStatusDiv.className = 'error';
                }
                console.error("Validation Error:", error.message);
                isValid = false;
            }

            if (!isValid) {
                return; // Stop submission if validation failed
            }

            // --- Construct the data payload in the required format ---
            const payload = {
                disasterType: disasterType,
                location: {
                    latitude: latitude,
                    longitude: longitude
                }
                // Only include optional fields if they have a non-empty, trimmed value
            };

            const trimmedDetails = details.trim();
            const trimmedMobile = mobileNumber.trim();

            if (trimmedDetails) {
                payload.details = trimmedDetails;
            }
            if (trimmedMobile) {
                payload.mobileNumber = trimmedMobile;
            }

            console.log("Sending payload to /api/v1/sos:", JSON.stringify(payload)); // For debugging

            // Send data to the backend API endpoint /api/v1/sos
            fetch("/api/v1/sos", { // <--- TARGET THE CORRECT ENDPOINT
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json" // Good practice to include Accept header
                },
                body: JSON.stringify(payload) // Convert JS object to JSON string
            })
            .then(response => {
                // Check if the response was successful (status code 2xx)
                 if (!response.ok) {
                    // If not okay, try to parse error details from JSON response
                     return response.json().then(errData => {
                         // Throw an error that includes details from the backend
                         const errMsg = errData.message || errData.error || `Request failed with status ${response.status}`;
                         throw new Error(errMsg);
                     }).catch(() => {
                        // If parsing JSON fails or no specific error message, throw a generic error
                         throw new Error(`Request failed with status ${response.status}`);
                     });
                 }
                 return response.json(); // Parse successful JSON response
             })
            .then(data => {
                console.log('Success response:', data);
                if (sosStatusDiv) {
                     // Use message from backend response if available
                     sosStatusDiv.textContent = data.message || 'SOS submitted successfully!';
                     sosStatusDiv.className = 'success';
                }
                sosForm.reset(); // Clear the form fields on success
             })
            .catch(error => {
                 console.error('Error submitting SOS:', error);
                 if (sosStatusDiv) {
                    // Display the specific error message caught
                    sosStatusDiv.textContent = `Error: ${error.message}`;
                    sosStatusDiv.className = 'error';
                 }
             });
        });
    }

    // --- Login Form Submission (No changes needed) ---
    if (document.getElementById("loginForm")) {
        document.getElementById("loginForm").addEventListener("submit", function(e) {
            e.preventDefault();
            const credentials = {
                username: document.getElementById("username").value,
                password: document.getElementById("password").value
            };

            fetch("/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(credentials),
                credentials: "include" // Important for sending session cookies
            })
            .then(response => {
                if (!response.ok) { // Check for non-2xx status codes
                     return response.json().then(err => {
                        throw new Error(err.message || 'Login request failed');
                     });
                 }
                 return response.json();
            })
            .then(data => {
                if (data.logged_in) {
                    window.location.href = "/dashboard"; // Redirect to dashboard
                } else {
                    // Display error message from backend if available, otherwise generic
                    document.getElementById("loginMessage").textContent = data.message || "Invalid credentials";
                }
            })
            .catch(error => {
                console.error("Login Error:", error);
                document.getElementById("loginMessage").textContent = error.message || "An error occurred during login.";
            });
        });
    }

    // --- Load SOS Messages and Announcements (No structural changes needed, but consider adding new fields to renderSOSMessages if desired for dashboard) ---
    if (document.getElementById("pendingSOS")) {
        loadSOSMessages(); // Initial load
        // Consider slightly longer interval if 5s is too frequent
        setInterval(loadSOSMessages, 10000); // e.g., every 10 seconds
    }

    // --- Broadcast Form Submission (No changes needed) ---
    if (document.getElementById("broadcastForm")) {
        document.getElementById("broadcastForm").addEventListener("submit", function(e) {
            e.preventDefault();
            const content = document.getElementById("broadcastMessage").value;
            if (!content.trim()) {
                alert("Broadcast message cannot be empty.");
                return;
            }

            fetch("/create_announcement", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content: content.trim() }),
                credentials: "include"
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.message || 'Failed to create announcement'); });
                }
                return response.json();
            })
            .then(data => {
                alert(data.message || "Announcement created."); // Use backend message
                document.getElementById("broadcastMessage").value = ""; // Clear textarea
                loadAnnouncements(); // Refresh announcement list
            })
            .catch(error => {
                console.error("Broadcast Error:", error);
                alert(`Error creating announcement: ${error.message}`);
            });
        });
    }

    // --- Initial Loads & Checks ---
    checkLoginStatus(); // Check if admin is logged in (relevant for dashboard page)
    loadAnnouncements(); // Load announcements on all pages where #announcementList exists
    setInterval(loadAnnouncements, 15000); // Refresh announcements periodically (e.g., 15s)
});

// --- Dashboard Functions (loadSOSMessages, renderSOSMessages, updateStatus) ---
// Consider adding mobile_number and disaster_type display in renderSOSMessages if needed on dashboard

function loadSOSMessages() {
    // Fetches all messages (backend returns a flat list now)
    fetch("/get_sos_messages", { credentials: "include" })
        .then(response => {
            if (response.status === 401) { // Handle unauthorized access gracefully
                console.warn("Unauthorized: Not logged in or session expired.");
                 // Optional: redirect to login or clear dashboard display
                 // window.location.href = '/login_page';
                 document.getElementById("pendingSOS").innerHTML = '<p>Please log in to view messages.</p>';
                 document.getElementById("underReviewSOS").innerHTML = '';
                 return null; // Stop further processing
            }
             if (!response.ok) {
                throw new Error(`Failed to load SOS messages (status ${response.status})`);
            }
            return response.json();
        })
        .then(data => {
            if (data === null) return; // Stop if unauthorized

            // Filter messages based on status for rendering into columns
            const pendingMessages = data.filter(sos => sos.status === 'Pending');
            const reviewMessages = data.filter(sos => sos.status === 'Under Review');
            // Add more filters if you have more columns (e.g., Resolved)

            renderSOSMessages(pendingMessages, "pendingSOS");
            renderSOSMessages(reviewMessages, "underReviewSOS");
        })
        .catch(error => console.error("Error loading SOS messages:", error));
}

function renderSOSMessages(messages, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return; // Safety check

    if (!messages || messages.length === 0) {
        container.innerHTML = '<p>No messages in this category.</p>';
        return;
    }

    // Render messages - currently shows name, location, message, status
    // TODO: Optionally add display for sos.mobile_number and sos.disaster_type here
    container.innerHTML = messages.map(sos => `
        <div class="sos-card" data-sos-id="${sos.id}">
            <p><strong>Name:</strong> ${sos.name || 'N/A'}</p>
            <p><strong>Location:</strong> ${sos.location || 'N/A'}</p>
            <p><strong>Message:</strong><br><pre>${sos.message || 'N/A'}</pre></p>
             ${sos.disaster_type ? `<p><strong>Disaster Type:</strong> ${sos.disaster_type}</p>` : ''}
             ${sos.mobile_number ? `<p><strong>Contact:</strong> ${sos.mobile_number}</p>` : ''}
             <p><strong>Status:</strong> ${sos.status || 'N/A'}</p>
             <p><small>Received: ${sos.created_at ? new Date(sos.created_at).toLocaleString() : 'N/A'}</small></p>
             <p><small>Source: ${sos.source || 'N/A'}</small></p>
             <div> <!-- Buttons container -->
                 ${sos.status === 'Pending' ?
                     '<button onclick="updateStatus(' + sos.id + ', \'Under Review\')">Mark as Under Review</button>' : ''}
                 ${sos.status === 'Under Review' ?
                     '<button onclick="updateStatus(' + sos.id + ', \'Resolved\')">Mark as Resolved</button>' : ''}
                 ${(sos.status === 'Pending' || sos.status === 'Under Review') ? /* Allow marking as False Alarm anytime before resolved */
                      '<button onclick="updateStatus(' + sos.id + ', \'False Alarm\')" style="background-color: #f0ad4e;">Mark as False Alarm</button>' : ''}
             </div>
         </div>
     `).join('');
     // Using <pre> for message to respect newlines from backend
     // Added display for optional disaster_type and mobile_number
     // Added display for created_at and source
     // Added False Alarm button
     // Separated buttons into a div
}


function loadAnnouncements() {
    const container = document.getElementById("announcementList");
    if (!container) return; // Don't run if the element doesn't exist on the page

    fetch("/get_announcements")
        .then(response => {
             if (!response.ok) { throw new Error('Failed to load announcements'); }
             return response.json();
        })
        .then(data => {
            if (data && data.length > 0) {
                container.innerHTML = data.map(ann => `
                    <div class="announcement-item">
                        <p>${ann.content}</p>
                        <small>Posted: ${new Date(ann.created_at).toLocaleString()}</small>
                    </div>
                `).join('');
            } else {
                container.innerHTML = '<p>No current announcements.</p>';
            }
        })
        .catch(error => {
            console.error("Error loading announcements:", error);
            if (container) { // Check again inside catch
                 container.innerHTML = '<p style="color: red;">Could not load announcements.</p>';
            }
        });
}

function updateStatus(sosId, newStatus) {
    console.log(`Updating SOS ID ${sosId} to status ${newStatus}`); // Debug log
    fetch(`/update_status/${sosId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
        credentials: "include"
    })
    .then(response => {
        if (!response.ok) {
             return response.json().then(err => { throw new Error(err.message || `Failed to update status`); });
        }
        return response.json();
    })
    .then(data => {
        // alert(data.message); // Using alert can be disruptive, maybe use a less intrusive notification
        console.log(data.message); // Log success message
        loadSOSMessages(); // Refresh the SOS list immediately
    })
    .catch(error => {
        console.error("Error updating status:", error);
        alert(`Error updating status: ${error.message}`); // Alert on error might be okay
    });
}

function checkLoginStatus() {
    // Only relevant if we are potentially on the dashboard page
    if (window.location.pathname.includes("/dashboard")) {
        fetch("/check_login", { credentials: "include" })
            .then(response => response.json())
            .then(data => {
                if (!data.logged_in) {
                    console.log("Not logged in, redirecting from dashboard.");
                    window.location.href = "/login_page"; // Redirect to login if not logged in on dashboard
                } else {
                    console.log("Logged in status checked on dashboard: OK");
                }
            })
            .catch(error => {
                 console.error("Error checking login status:", error);
                 // Maybe redirect to login on error too?
                 // window.location.href = "/login_page";
            });
    }
}

function logout() {
    fetch("/logout", { method: "GET", credentials: "include" }) // Changed to GET as logout usually is
        .then(response => response.json())
        .then(() => {
            console.log("Logged out, redirecting to home.");
            window.location.href = "/"; // Redirect to home page after logout
        })
        .catch(error => {
            console.error("Logout error:", error);
            // Still redirect even if fetch fails?
            window.location.href = "/";
        });
}

