const express = require('express');
const AWS = require('aws-sdk');
const app = express();
const port = process.env.PORT || 3000;

// Middleware to parse JSON data
app.use(express.json());

// Configure AWS SDK with your Access Key ID and Secret Access Key
AWS.config.update({
  accessKeyId: 'AKIAVZH4SBSY6M4YGRUO',
  secretAccessKey: 'wg12E96XuenOao/XGmWfY0bzBjl8Ag+yEv9XzzGx'
});

// Create a new instance of the S3 service
const s3 = new AWS.S3();

// Endpoint to handle photo upload
app.post('/upload', (req, res) => {
  const photoData = req.body.photo;
  const base64Data = photoData.replace(/^data:image\/\w+;base64,/, '');
  const buffer = Buffer.from(base64Data, 'base64');

  // Set the parameters for the S3 upload
  const params = {
    Bucket: 'bucketeer-0b6051cb-e249-4102-87b3-8fba714cf40e',
    Key: `photos/photo_${Date.now()}.png`,
    Body: buffer,
    ContentEncoding: 'base64',
    ContentType: 'image/png'
  };

  // Upload the photo to Bucketeer
  s3.upload(params, (err, data) => {
    if (err) {
      console.error('Error uploading photo to Bucketeer:', err);
      res.status(500).json({ error: 'Failed to upload photo' });
    } else {
      console.log('Photo uploaded to Bucketeer:', data.Location);
      res.status(200).json({ message: 'Photo uploaded successfully' });
    }
  });
});

// Start the server
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});