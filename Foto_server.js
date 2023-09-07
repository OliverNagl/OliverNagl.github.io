const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

// Middleware to parse JSON data
app.use(express.json());

// Endpoint to handle photo upload
app.post('/upload', (req, res) => {
  const photoData = req.body.photo;
  // Process the photo data as needed (e.g., save it to a file, store it in a database, etc.)
  // Replace the following code with your own logic

  // Example response
  res.status(200).json({ message: 'Photo uploaded successfully!' });
});

// Start the server
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});

const { MongoClient } = require('mongodb');

// Connection URL and database name
const url = 'mongodb://localhost:27017';
const dbName = 'your-database-name';

// Create a new MongoClient
const client = new MongoClient(url);

// Connect to the MongoDB server
client.connect(function(err) {
  if (err) {
    console.error('Error connecting to the database:', err);
  } else {
    console.log('Connected to the database');

    // Database instance
    const db = client.db(dbName);

    // Use the database for further operations
    // ...
  }
});

app.post('/upload', (req, res) => {
    const photoData = req.body.photo;

    // Store the photo in the database
    const collection = db.collection('photos');
    collection.insertOne({ photo: photoData }, function(err, result) {
      if (err) {
        console.error('Error storing photo in the database:', err);
        res.status(500).json({ error: 'Failed to store photo in the database' });
      } else {
        console.log('Photo stored in the database');
        res.status(200).json({ message: 'Photo uploaded and stored successfully' });
      }
    });
  });