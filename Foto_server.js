const express = require('express');
const app = express();
const port = process.env.PORT || 3000;
const AWS = require('aws-sdk');
const cors = require('cors');
const busboy = require('busboy');
const stream = require('stream');
const sharp = require('sharp'); // For image compression

app.use(cors());

const s3 = new AWS.S3();

app.get('/', (req, res) => {
  res.sendFile(__dirname + '/public/FotoUpload.html');
});

// Endpoint to handle photo upload
app.post('/upload', (req, res) => {
  const busboyInstance = busboy({ headers: req.headers });
  const chunks = [];

  busboyInstance.on('file', (fieldname, file, filename, encoding, mimetype) => {
    const writableStreamBuffer = new stream.PassThrough();

    // Compress and convert to JPEG
    const transformer = sharp()
      .jpeg({ quality: 80 });

    file.pipe(transformer).pipe(writableStreamBuffer);

    writableStreamBuffer.on('data', (chunk) => {
      chunks.push(chunk);
    });

    writableStreamBuffer.on('end', () => {
      const buffer = Buffer.concat(chunks);
      const params = {
        Bucket: process.env.BUCKETEER_BUCKET_NAME,
        Key: `photos/photo-${Date.now()}.jpg`, // Use a unique key for each photo
        Body: buffer,
        ContentType: 'image/jpeg', // Set the content type accordingly
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
  });

  req.pipe(busboyInstance);
});

// Start the server
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
