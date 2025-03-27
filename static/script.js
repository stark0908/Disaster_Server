document.addEventListener("DOMContentLoaded", function() {
    // SOS Form Submission
    // Update the SOS form submission handler
if (document.getElementById("sosForm")) {
    document.getElementById("sosForm").addEventListener("submit", function(e) {
        e.preventDefault();
        
        const formData = {
            name: document.getElementById("name").value,
            location: document.getElementById("location").value,
            message: document.getElementById("message").value
        };

        fetch("/submit_sos", {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify(formData)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.message); });
            }
            return response.json();
        })
        .then(data => {
            alert(data.message);
            document.getElementById("sosForm").reset();
        })
        .catch(error => {
            alert(error.message || "Failed to submit SOS");
            console.error("Error:", error);
        });
    });
}

    // Login Form Submission
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
                credentials: "include"
            })
            .then(response => response.json())
            .then(data => {
                if (data.logged_in) {
                    window.location.href = "/dashboard";
                } else {
                    document.getElementById("loginMessage").textContent = "Invalid credentials";
                }
            })
            .catch(error => console.error("Error:", error));
        });
    }

    // Load SOS Messages and Announcements
    if (document.getElementById("pendingSOS")) {
        loadSOSMessages();
        setInterval(loadSOSMessages, 5000);
    }

    // Broadcast Form Submission
    if (document.getElementById("broadcastForm")) {
        document.getElementById("broadcastForm").addEventListener("submit", function(e) {
            e.preventDefault();
            const content = document.getElementById("broadcastMessage").value;

            fetch("/create_announcement", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ content }),
                credentials: "include"
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                document.getElementById("broadcastMessage").value = "";
                loadAnnouncements();
            })
            .catch(error => console.error("Error:", error));
        });
    }

    // Check login status
    checkLoginStatus();
    loadAnnouncements();
    setInterval(loadAnnouncements, 10000);
});

function loadSOSMessages() {
    fetch("/get_sos_messages", { credentials: "include" })
        .then(response => response.json())
        .then(data => {
            renderSOSMessages(data.pending, "pendingSOS");
            renderSOSMessages(data.under_review, "underReviewSOS");
        })
        .catch(error => console.error("Error:", error));
}

function renderSOSMessages(messages, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = messages.map(sos => `
        <div class="sos-card">
            <p><strong>Name:</strong> ${sos.name}</p>
            <p><strong>Location:</strong> ${sos.location}</p>
            <p><strong>Message:</strong> ${sos.message}</p>
            <p><strong>Status:</strong> ${sos.status}</p>
            ${sos.status === 'Pending' ? 
                '<button onclick="updateStatus(' + sos.id + ', \'Under Review\')">Mark as Under Review</button>' : 
                '<button onclick="updateStatus(' + sos.id + ', \'Resolved\')">Mark as Resolved</button>'}
        </div>
    `).join('');
}

function loadAnnouncements() {
    fetch("/get_announcements")
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById("announcementList");
            if (container) {
                container.innerHTML = data.map(ann => `
                    <div class="announcement">
                        <p><strong>${new Date(ann.created_at).toLocaleString()}:</strong> ${ann.content}</p>
                    </div>
                `).join('');
            }
        })
        .catch(error => console.error("Error:", error));
}

function updateStatus(sosId, newStatus) {
    fetch(`/update_status/${sosId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
        credentials: "include"
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        loadSOSMessages();
    })
    .catch(error => console.error("Error:", error));
}

function checkLoginStatus() {
    fetch("/check_login", { credentials: "include" })
        .then(response => response.json())
        .then(data => {
            if (!data.logged_in && window.location.pathname === "/dashboard") {
                window.location.href = "/";
            }
        });
}

function logout() {
    fetch("/logout", { credentials: "include" })
        .then(response => response.json())
        .then(() => window.location.href = "/");
}