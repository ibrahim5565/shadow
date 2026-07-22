const { spawn } = require('child_process');
const server = spawn('python', ['-m', 'http.server', '5000'], {
    shell: true,
    stdio: 'inherit'
});

server.on('error', (err) => {
    console.error('Failed to start server:', err);
});

server.on('close', (code) => {
    console.log(`Server process exited with code ${code}`);
});
