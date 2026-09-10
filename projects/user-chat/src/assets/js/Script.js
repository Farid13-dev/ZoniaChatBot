function openChat() {
    document.getElementById("chat-modal").style.display = "block";
}

function closeChat() {
    document.getElementById("chat-modal").style.display = "none";
}

function sendMessage() {
    var userInput = document.getElementById("user-input").value;
    var chatDisplay = document.getElementById("chat-display");

    // Agregar mensaje del usuario al chat
    var userMessage = document.createElement("div");
    userMessage.className = "message user-message";
    userMessage.textContent = userInput;
    chatDisplay.appendChild(userMessage);

    // Simular respuesta del chatbot
    var botMessage = document.createElement("div");
    botMessage.className = "message bot-message";
    botMessage.textContent = generateResponse(userInput); // Aquí debes implementar la lógica del chatbot
    chatDisplay.appendChild(botMessage);

    // Limpiar el campo de entrada
    document.getElementById("user-input").value = "";

    // Scroll automático al nuevo mensaje
    chatDisplay.scrollTop = chatDisplay.scrollHeight;
}

// Función para generar una respuesta del chatbot (aquí solo devuelve una respuesta predeterminada)
function generateResponse(userInput) {
    return "¡Hola! Soy un chatbot. Gracias por tu mensaje: " + userInput;
}
