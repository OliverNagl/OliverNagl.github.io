const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

const AWS = require('aws-sdk');
const cors = require('cors');
app.use(cors());
// Middleware to parse JSON data
app.use(express.json());
app.use(express.static('public'));

const s3 = new AWS.S3();

app.get('/', (req, res) => {
  res.sendFile(__dirname + '/public/FotoUpload.html');
});

// Endpoint to handle photo upload
app.post('/upload', (req, res) => {
  const photoData = req.body.photo;
  const base64Data = photoData.replace(/^data:image\/\w+;base64,/, '');
  const buffer = Buffer.from(base64Data, 'base64');

  const params = {
    Bucket: process.env.BUCKETEER_BUCKET_NAME, // Replace with your bucket name
    Key: `photos/photo-${Date.now()}.png`, // Use a unique key for each photo
    Body: buffer,
    ContentType: 'image/png', // Set the content type accordingly
  };

  s3.upload(params, (err, data) => {
    if (err) {
      console.error('Error uploading photo to Bucketeer:', err);
      res.status(500).json({ error: 'Failed to upload photo' });
    } else {
      console.log('Photo uploaded to Bucketeer');
      res.status(200).json({ message: 'Photo uploaded successfully' });
    }
  });
});

// Start the server
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});