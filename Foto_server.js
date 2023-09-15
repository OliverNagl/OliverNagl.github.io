const express = require('express');
const app = express();
const port = process.env.PORT || 3000;
const AWS = require('aws-sdk');
const cors = require('cors');
const busboy = require('busboy');
const stream = require('stream');
const sharp = require('sharp'); // For image compression

app.use(cors());
// Serve static files from the "public" directory
app.use(express.static('public'));

AWS.config.update({
  accessKeyId: process.env.BUCKETEER_AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.BUCKETEER_AWS_SECRET_ACCESS_KEY,
  // Optionally, you can specify the region as well
  region: process.env.BUCKETEER_AWS_REGION, // Replace with your desired AWS region
});

const s3 = new AWS.S3();

app.get('/', (req, res) => {
  res.sendFile(__dirname + '/public/FotoUpload.html');
});


// Endpoint to handle photo upload
app.post('/upload', (req, res) => {
  const busboyInstance = busboy({ headers: req.headers });
  const chunks = [];

  busboyInstance.on('file', (fieldname, file, filename, encoding, mimetype) => {
    const transformer = sharp()
      .resize({ width: 1024 }) // Set the maximum width you desire
      .jpeg({ quality: 80 });

    file.pipe(transformer, { end: false }).pipe(res);

    transformer.on('data', (chunk) => {
      chunks.push(chunk);
    });

    transformer.on('end', () => {
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
          return res.status(500).json({ error: 'Failed to upload photo' });
        } else {
          console.log('Photo uploaded to Bucketeer');
          // Only send a success response here, no need to send another response below
          return res.status(200).json({ message: 'Photo uploaded successfully' });
        }
      });
    });
  });

  req.pipe(busboyInstance);
});


app.get('/photos', (req, res) => {
  const params = {
    Bucket: process.env.BUCKETEER_BUCKET_NAME, // Replace with your bucket name
  };

  s3.listObjects(params, (err, data) => {
    if (err) {
      console.error('Error listing photos:', err);
      res.status(500).json({ error: 'Failed to list photos' });
    } else {
      const photos = data.Contents.map(photo => ({
        key: photo.Key,
        url: s3.getSignedUrl('getObject', { Bucket: params.Bucket, Key: photo.Key }),
      }));
      res.json({ photos });
    }
  });
});

// Start the server
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});





