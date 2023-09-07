const express = require('express');
const app = express();
const port = process.env.PORT || 3000;
const { Pool } = require('pg');

// Middleware to parse JSON data
app.use(express.json());
app.use(express.static('public'));

// Configure PostgreSQL connection
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: {
    rejectUnauthorized: false,
  },
});

app.get('/', (req, res) => {
  res.sendFile(__dirname + '/public/index.html');
});

// Endpoint to handle photo upload
app.post('/upload', (req, res) => {
  const photoData = req.body.photo;
  const base64Data = photoData.replace(/^data:image\/\w+;base64,/, '');
  const buffer = Buffer.from(base64Data, 'base64');

  // Insert the photo into the PostgreSQL database
  pool.query('INSERT INTO photos (photo_data) VALUES ($1)', [buffer], (err, result) => {
    if (err) {
      console.error('Error uploading photo to PostgreSQL:', err);
      res.status(500).json({ error: 'Failed to upload photo' });
    } else {
      console.log('Photo uploaded to PostgreSQL');
      res.status(200).json({ message: 'Photo uploaded successfully' });
    }
  });
});

// Start the server
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});