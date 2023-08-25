var canvas = document.getElementById('game');
var context = canvas.getContext('2d');

var grid = 16;
var count = 0;

var snake = {
  x: 160,
  y: 160,
  dx: grid,
  dy: 0,
  cells: [],
  maxCells: 4
};

var apple = {
  x: 320,
  y: 320
};

var gameStarted = false; // Add this line

function getRandomInt(min, max) {
  return Math.floor(Math.random() * (max - min)) + min;
}

function loop() {
  if (!gameStarted) { // Add this line
    return;
  }

  requestAnimationFrame(loop);

  // Change this line to slow down the snake
  if (++count < 10) {
    return;
  }

  count = 0;
  context.clearRect(0,0,canvas.width,canvas.height);

  snake.x += snake.dx;
  snake.y += snake.dy;

  // Modify these conditions to make the snake die when it hits the wall
  if (snake.x < 0 || snake.x >= canvas.width || snake.y < 0 || snake.y >= canvas.height) {
    gameStarted = false; // Add this line
    snake.x = 160;
    snake.y = 160;
    snake.cells = [];
    snake.maxCells = 4;
    snake.dx = grid;
    snake.dy = 0;
    apple.x = getRandomInt(0, 25) * grid;
    apple.y = getRandomInt(0, 25) * grid;
    return;
  }

  // The rest of the code remains the same
}

// Add this event listener to start the game when the canvas is clicked
canvas.addEventListener('click', function() {
  gameStarted = true;
  loop();
});