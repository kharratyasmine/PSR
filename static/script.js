document.addEventListener("DOMContentLoaded", function() {
    // Handle file upload
    document.getElementById('upload-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        const files = document.getElementById('file-input').files;
        const allowedExtensions = ['.xls', '.xlsx'];
        let error = '';
    
        for (const file of files) {
            if (!allowedExtensions.some(ext => file.name.endsWith(ext))) {
                error = `Invalid file format for ${file.name}. Please upload Excel files only.`;
                break;
            }
        }
    
        if (error) {
            document.getElementById('message').innerText = error;
            return;
        }
    
        const formData = new FormData();
        for (const file of files) {
            formData.append('files', file);
        }
    
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData,
        });
        const result = await response.json();
        document.getElementById('message').innerText = result.error || result.message;

        if (!result.error) {
        const uploadedFilesBody = document.getElementById('uploaded-files-body');
        result.files.forEach(file => {
            const newRow = document.createElement('tr');
            newRow.innerHTML = `
                <td>${file.filename}</td>
                <td>${file.uploaded_at}</td>
                <td><a href="/download_upload/${file.filename}" download>Download</a></td>
                <td>
                    <button id="deletebtn" class="btn btn-danger btn-sm delete-file" data-filename="${file.filename}">Delete</button>
                </td>
            `;
            // Prepend the new row to the table body
            uploadedFilesBody.prepend(newRow);
        });
    }
});
    

    // Handle adding a new public holiday
    document.getElementById("add-holiday-form").addEventListener("submit", function(event) {
        event.preventDefault();
        const holidayName = document.getElementById("holiday_name").value;
        const holidayDate = document.getElementById("holiday_date").value;

        fetch("/add_public_holiday", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ name: holidayName, date: holidayDate })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
            } else {
                const holidaysList = document.getElementById("public-holidays-list");
                const newListItem = document.createElement("li");
                newListItem.className = "list-group-item d-flex justify-content-between align-items-center";
                newListItem.innerHTML = `
                    ${holidayName} - ${holidayDate}
                    <button class="btn btn-danger btn-sm delete-holiday" data-date="${holidayDate}" data-name="${holidayName}">Delete</button>
                `;
                holidaysList.appendChild(newListItem);
                document.getElementById("holiday_name").value = "";  // Clear the input field
                document.getElementById("holiday_date").value = "";  // Clear the input field
            }
        })
        .catch(error => console.error("Error:", error));
    });

    // Handle deleting a public holiday
    document.getElementById("public-holidays-list").addEventListener("click", function(event) {
        if (event.target.classList.contains("delete-holiday")) {
            const holidayDate = event.target.getAttribute("data-date");
            const holidayName = event.target.getAttribute("data-name");

            if (confirm(`Are you sure you want to delete the holiday "${holidayName}" on ${holidayDate}?`)) {
                fetch("/delete_public_holiday", {
                    method: "DELETE",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ date: holidayDate, name: holidayName })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                    } else {
                        event.target.parentElement.remove();
                    }
                })
                .catch(error => console.error("Error:", error));
            }
        }
    });

    // Handle exporting holidays data
    document.getElementById("export-btn").addEventListener("click", function() {
        fetch("/export")
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
            } else {
                const exportedFilesBody = document.getElementById("exported-files-body");
                const newRow = document.createElement("tr");
    
                newRow.innerHTML = `
                    <td>${data.exported_file}</td>
                    <td>${data.created_at}</td>
                    <td><a href="/exported/${data.exported_file}" download>Download</a></td>
                    <td>
                        <button id="deletebtn" class="btn btn-danger btn-sm delete-export" data-filename="${data.exported_file}">Delete</button>
                    </td>
                `;
                
                // Prepend the new row to the table body
                exportedFilesBody.prepend(newRow);

                // Trigger the file download
                const downloadLink = document.createElement('a');
                downloadLink.href = `/download/${data.exported_file}`;
                downloadLink.download = data.exported_file;
                downloadLink.click();
            }
        })
        .catch(error => console.error("Error:", error));
    });
    

    // Handle deleting an uploaded file
    document.getElementById("uploaded-files-table").addEventListener("click", function(event) {
        if (event.target.classList.contains("delete-file")) {
            const filename = event.target.getAttribute("data-filename");

            if (confirm(`Are you sure you want to delete the file "${filename}"?`)) {
                fetch(`/delete_file/${filename}`, {
                    method: "DELETE"
                })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                    } else {
                        event.target.closest("tr").remove();
                    }
                })
                .catch(error => console.error("Error:", error));
            }
        }
    });
    // Handle deleting an exported file
    document.getElementById("exported-files-table").addEventListener("click", function(event) {
        if (event.target.classList.contains("delete-export")) {
            const filename = event.target.getAttribute("data-filename");

            if (confirm(`Are you sure you want to delete the file "${filename}"?`)) {
                fetch(`/delete_export/${filename}`, {
                    method: "DELETE"
                })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                    } else {
                        event.target.closest("tr").remove();
                    }
                })
                .catch(error => console.error("Error:", error));
            }
        }
    });
});
