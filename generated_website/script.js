// Demo Widget Interactivity
function handleDemoSubmit() {
    const input = document.getElementById('demo-input').value.trim();
    const output = document.getElementById('demo-output');
    
    if (input) {
        output.innerHTML = `<p class="text-gray-800">You asked: <strong>"${input}"</strong></p>
                           <p class="text-gray-600">Lumina AI: "This is a simulated response to your query."</p>`;
    } else {
        output.innerHTML = '<p class="text-gray-600">Please enter a query to see the response.</p>';
    }
}

// Self-Testing Assertions
if (typeof window !== 'undefined') {
    // Verify DOM elements exist
    const heroSection = document.querySelector('.hero');
    const featuresSection = document.querySelector('#features');
    const demoSection = document.querySelector('#demo');
    const footer = document.querySelector('footer');
    
    if (!heroSection || !featuresSection || !demoSection || !footer) {
        console.error('Critical UI elements missing in the DOM');
    } else {
        console.log('All UI elements are properly initialized');
    }
    
    // Verify demo widget functionality
    const demoInput = document.getElementById('demo-input');
    const demoOutput = document.getElementById('demo-output');
    
    if (demoInput && demoOutput) {
        console.log('Demo widget elements are correctly initialized');
    } else {
        console.error('Demo widget elements not found');
    }
}