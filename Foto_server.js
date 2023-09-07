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
app.post('postgres://zkeursujlkqvvy:7fc8b086ccfdda6d83912e3f70547f604cb5e7cbccfc52200f7ad62e9117b392@ec2-52-209-225-31.eu-west-1.compute.amazonaws.com:5432/ddous02qo0iscu', (req, res) => {
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