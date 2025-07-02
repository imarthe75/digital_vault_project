const API_BASE_URL = 'http://localhost:5000/vault'; // Asegúrate que coincida con tu backend

// --- Funciones para manejar respuestas y errores ---
async function handleResponse(response, statusElement) {
    if (response.ok) {
        const data = await response.json();
        statusElement.textContent = `Éxito: ${data.message || JSON.stringify(data)}`;
        statusElement.className = 'success';
        return data;
    } else {
        const errorData = await response.json();
        statusElement.textContent = `Error: ${errorData.error || response.statusText}`;
        statusElement.className = 'error';
        throw new Error(errorData.error || response.statusText);
    }
}

// --- Subir Archivo ---
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const uploadStatus = document.getElementById('uploadStatus');
    uploadStatus.textContent = 'Subiendo...';
    uploadStatus.className = '';

    const fileInput = document.getElementById('uploadFile');
    const userId = document.getElementById('uploadUserId').value;
    const metadata = document.getElementById('uploadMetadata').value;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('user_id', userId);
    formData.append('metadata', metadata);

    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData,
        });
        await handleResponse(response, uploadStatus);
        // Opcional: limpiar formulario o actualizar lista de archivos
    } catch (error) {
        console.error('Error al subir:', error);
    }
});

// --- Descargar Archivo ---
document.getElementById('downloadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const downloadStatus = document.getElementById('downloadStatus');
    downloadStatus.textContent = 'Descargando...';
    downloadStatus.className = '';

    const fileId = document.getElementById('downloadFileId').value;
    const userId = document.getElementById('downloadUserId').value;

    try {
        const response = await fetch(`${API_BASE_URL}/${fileId}?user_id=${userId}`, {
            method: 'GET',
        });

        if (response.ok) {
            const blob = await response.blob();
            const filename = response.headers.get('Content-Disposition')?.split('filename=')[1] || `file_${fileId}`;
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename.replace(/"/g, ''); // Eliminar comillas si las hay
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            downloadStatus.textContent = 'Descarga iniciada.';
            downloadStatus.className = 'success';
        } else {
            const errorText = await response.text(); // Podría ser JSON o texto plano
            downloadStatus.textContent = `Error al descargar: ${errorText}`;
            downloadStatus.className = 'error';
        }
    } catch (error) {
        console.error('Error al descargar:', error);
        downloadStatus.textContent = `Error de red: ${error.message}`;
        downloadStatus.className = 'error';
    }
});

// --- Eliminar Archivo ---
document.getElementById('deleteForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const deleteStatus = document.getElementById('deleteStatus');
    deleteStatus.textContent = 'Eliminando...';
    deleteStatus.className = '';

    const fileId = document.getElementById('deleteFileId').value;
    const userId = document.getElementById('deleteUserId').value;

    try {
        const response = await fetch(`${API_BASE_URL}/${fileId}?user_id=${userId}`, {
            method: 'DELETE',
        });
        await handleResponse(response, deleteStatus);
        // Opcional: limpiar ID o actualizar lista
    } catch (error) {
        console.error('Error al eliminar:', error);
    }
});

// --- Listar Archivos de Usuario ---
document.getElementById('listForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileListDiv = document.getElementById('fileList');
    fileListDiv.innerHTML = 'Cargando archivos...';

    const userId = document.getElementById('listUserId').value;

    try {
        const response = await fetch(`${API_BASE_URL}/user/${userId}?requester_id=${userId}`);
        if (response.ok) {
            const files = await response.json();
            if (files.length === 0) {
                fileListDiv.innerHTML = '<p>No hay archivos para este usuario.</p>';
                return;
            }

            const ul = document.createElement('ul');
            files.forEach(file => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <strong>${file.original_filename}</strong> (ID: ${file.file_id})<br>
                    <span>Tipo: ${file.mimetype || 'N/A'}, Tamaño: ${file.size_bytes} bytes</span><br>
                    <span>Subido: ${new Date(file.upload_timestamp).toLocaleString()}</span><br>
                    <span>Metadata: ${JSON.stringify(file.metadata)}</span>
                `;
                ul.appendChild(li);
            });
            fileListDiv.innerHTML = '';
            fileListDiv.appendChild(ul);
        } else {
            const errorData = await response.json();
            fileListDiv.innerHTML = `<p class="error">Error al listar archivos: ${errorData.error || response.statusText}</p>`;
        }
    } catch (error) {
        console.error('Error al listar archivos:', error);
        fileListDiv.innerHTML = `<p class="error">Error de red: ${error.message}</p>`;
    }
});