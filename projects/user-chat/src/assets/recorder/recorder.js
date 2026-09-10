// Import necessary modules
//import createLinkFromAudioBuffer from './exporter.mjs';

// Enum for recorder states
const RecorderStates = {
    UNINITIALIZED: 0,
    RECORDING: 1,
    PAUSED: 2,
    FINISHED: 3
};

// Define the AudioRecorder class
class AudioRecorder {
    constructor(workletNodeProcessorUrl) {
        this.initialized_ = false;

        this.recordingNode = null;
        this.analyserNode = null;
        this.visualizers = [];

        this.recordingState = RecorderStates.UNINITIALIZED;

        this.workletNodeProcessorUrl = workletNodeProcessorUrl;

        // callback for recording length updates
        this.onRecordingLengthUpdated = null;

        // callback for recording state changes
        this.onRecordingStateChanged = null;

        // callback for recording max length reached
        this.onRecordingMaxLenReached = null;

        // callback for download ready
        this.onDownloadReady = null;

        // callback for visualizer creation
        this.onCreateVisualizers = null;
    }

    /**
     * Check if the AudioRecorder is initialized.
     */
    isInitialized() {
        return this.initialized_;
    }

    /**
     * Initialize the AudioContext and set up the recording chain.
     * @return {Promise<void>}
     */
    async initContext() {
        try {
            this.context = new AudioContext();
            await this.initializeAudio();
            this.changeRecordingStatus();
            this.initialized_ = true;
        } catch (error) {
            console.error('Failed to initialize context:', error);
        }
    }

    /**
     * Define overall audio chain and initializes all functionality.
     * @return {Promise<void>}
     */
    async initializeAudio() {
        try {
            if (this.context.state === 'suspended') {
                await this.context.resume();
            }

            // Get user's microphone and connect it to the AudioContext.
            const micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: false,
                    autoGainControl: false,
                    noiseSuppression: false,
                    latency: 0
                }
            });

            const micSourceNode = new MediaStreamAudioSourceNode(this.context, { mediaStream: micStream });
            const gainNode = new GainNode(this.context);
            this.analyserNode = new AnalyserNode(this.context);

            const recordingProperties = {
                numberOfChannels: micSourceNode.channelCount,
                sampleRate: this.context.sampleRate,
                maxFrameCount: this.context.sampleRate * 300
            };

            this.recordingNode = await this.setupRecordingWorkletNode(recordingProperties);

            const visualizerCallback = this.setupVisualizers();
            const recordingCallback = this.handleRecording(this.recordingNode.port, recordingProperties);

            this.recordingNode.port.onmessage = (event) => {
                if (event.data.message === 'UPDATE_VISUALIZERS') {
                    visualizerCallback(event);
                } else {
                    recordingCallback(event);
                }
            };

            gainNode.gain.value = 0;

            micSourceNode.connect(this.analyserNode).connect(this.recordingNode).connect(gainNode).connect(this.context.destination);
        } catch (error) {
            console.error('Failed to initialize audio:', error);
        }
    }

    /**
     * Create and set up a WorkletNode to record audio from a microphone.
     * @param {object} recordingProperties
     * @return {AudioWorkletNode} Recording node related components for
     * the app.
     */
    async setupRecordingWorkletNode(recordingProperties) {
        await this.context.audioWorklet.addModule(this.workletNodeProcessorUrl);

        const WorkletRecordingNode = new AudioWorkletNode(this.context, 'recording-processor', {
            processorOptions: recordingProperties
        });

        return WorkletRecordingNode;
    }

    /**
     * Set events and define callbacks for recording start/stop events.
     * @param {MessagePort} processorPort Processor port to send recording
     * state events to.
     * @param {object} recordingProperties Microphone channel count, for
     * accurate recording length calculations.
     * @return {function} Callback for recording-related events.
     */
    handleRecording(processorPort, recordingProperties) {
        let recordingLength = 0;

        // If the max length is reached, we can no longer record.
        const recordingEventCallback = async (event) => {
            if (event.data.message === 'MAX_RECORDING_LENGTH_REACHED') {
                // this.recordText.textContent = 'Reached the maximum length of';
                this.onRecordingMaxLenReached();
                this.recordingState = RecorderStates.FINISHED;
                this.changeRecordingStatus();

                this.createRecord(recordingProperties, recordingLength, this.context.sampleRate, event.data.buffer);
            }
            if (event.data.message === 'UPDATE_RECORDING_LENGTH') {
                recordingLength = event.data.recordingLength;

                this.updateRecordingLength(recordingLength);
            }
            if (event.data.message === 'SHARE_RECORDING_BUFFER') {
                this.createRecord(recordingProperties, recordingLength, this.context.sampleRate, event.data.buffer);
            }
        };

        if (this.recordingState === RecorderStates.UNINITIALIZED) {
            this.recordingState = RecorderStates.RECORDING;
            processorPort.postMessage({
                message: 'UPDATE_RECORDING_STATE',
                setRecording: true
            });
            this.changeRecordingStatus();
        }

        return recordingEventCallback;
    }

    /**
     * Start recording audio from the microphone.
     */
    startRecording() {
        this.recordingState = RecorderStates.RECORDING;
        this.recordingNode.port.postMessage({
            message: 'UPDATE_RECORDING_STATE',
            setRecording: true
        });
        this.changeRecordingStatus();
    }

    /**
     * Pause recording audio from the microphone.
     */
    stopRecording() {
        this.recordingState = RecorderStates.PAUSED;
        this.recordingNode.port.postMessage({
            message: 'UPDATE_RECORDING_STATE',
            setRecording: false
        });
        this.changeRecordingStatus();
    }

    /**
     * Clean up the audio context and stop the media stream.
     */
    cleanup() {
        if (this.context) {
            this.context.close();
        }
        // Stop media stream if needed
    }

    /**
     * Update the recording length in the UI.
     * @param {number} recordingLength The current length of recording.
     */
    updateRecordingLength(recordingLength) {
        if (this.onRecordingLengthUpdated) {
            this.onRecordingLengthUpdated(Math.round((recordingLength / this.context.sampleRate) * 100) / 100);
        }
    }

    /**
     * Change the recording status and call the callback.
     */
    changeRecordingStatus() {
        let isRecording = this.recordingState === RecorderStates.RECORDING;

        if (this.onRecordingStateChanged) {
            this.onRecordingStateChanged(isRecording);
        }
    }

    /**
     * Prepare the downloadable audio file.
     */
    prepareDownload(audioFileUrl) {
        if (this.onDownloadReady) {
            this.onDownloadReady(audioFileUrl);
        }
    }

    /**
     * Set up and handles calculations and rendering for all visualizers.
     * @return {function} Callback for visualizer events from the
     * processor.
     */
    setupVisualizers() {
        let initialized = false;

        // Create visualizers
        this.visualizers = this.onCreateVisualizers(this.analyserNode);

        // Wait for processor to start sending messages before beginning to
        // render.
        const visualizerEventCallback = async (event) => {
            if (event.data.message === 'UPDATE_VISUALIZERS') {
                if (!initialized) {
                    initialized = true;
                    draw();
                }
            }
        };

        const draw = () => {
            if (this.recordingState === RecorderStates.RECORDING) {
                // check visualizers are enabled and it is an array
                if (this.visualizers && Array.isArray(this.visualizers) && this.visualizers.length > 0) {
                    this.visualizers.forEach((visualizer) => {
                        visualizer.draw();
                    });
                }
            }

            // Request render frame regardless.  If visualizers are disabled,
            // function can still wait for enable.
            requestAnimationFrame(draw);
        };

        return visualizerEventCallback;
    }

    /**
     * Create the downloadable .wav file for the recorded voice and set
     * the download button clickable.
     * @param {object} recordingProperties Microphone channel count, for
     * accurate recording length calculations.
     * @param {number} recordingLength The current length of recording.
     * @param {number} sampleRate The sample rate of audio content.
     * @param {number[]} dataBuffer The dataBuffer of recording.
     */
    createRecord(recordingProperties, recordingLength, sampleRate, dataBuffer) {
        const recordingBuffer = this.context.createBuffer(recordingProperties.numberOfChannels, recordingLength, sampleRate);

        for (let i = 0; i < recordingProperties.numberOfChannels; i++) {
            recordingBuffer.copyToChannel(dataBuffer[i], i, 0);
        }

        // const audioFileUrl = createLinkFromAudioBuffer(recordingBuffer, true);
        //
        // this.prepareDownload(audioFileUrl);
      const blob = _createWaveFileBlobFromAudioBuffer(recordingBuffer, true);

// Solo si deseas crear un link de descarga visible:
// this.prepareDownload(URL.createObjectURL(blob));

// ✅ Aquí te aseguras de pasar el blob directo
if (this.onDownloadReady) {
  this.onDownloadReady(blob);
}

    }
}

// Export the AudioRecorder class
// export default AudioRecorder;

/**
 * @license Copyright (c) 2016 Hongchan Choi. MIT License.
 * @fileOverview Canopy PCM wave file exporter.
 * @return {function} create link function
 */

function _writeStringToArray(aString, targetArray, offset) {
    for (let i = 0; i < aString.length; ++i) {
        targetArray[offset + i] = aString.charCodeAt(i);
    }
}

function _writeInt16ToArray(aNumber, targetArray, offset) {
    aNumber = Math.floor(aNumber);
    targetArray[offset + 0] = aNumber & 255; // byte 1
    targetArray[offset + 1] = (aNumber >> 8) & 255; // byte 2
}

function _writeInt32ToArray(aNumber, targetArray, offset) {
    aNumber = Math.floor(aNumber);
    targetArray[offset + 0] = aNumber & 255; // byte 1
    targetArray[offset + 1] = (aNumber >> 8) & 255; // byte 2
    targetArray[offset + 2] = (aNumber >> 16) & 255; // byte 3
    targetArray[offset + 3] = (aNumber >> 24) & 255; // byte 4
}

// Return the bits of the float as a 32-bit integer value.  This
// produces the raw bits; no intepretation of the value is done.
function _floatBits(f) {
    const buf = new ArrayBuffer(4);
    new Float32Array(buf)[0] = f;
    const bits = new Uint32Array(buf)[0];
    // Return as a signed integer.
    return bits | 0;
}

function _writeAudioBufferToArray(audioBuffer, targetArray, offset, bitDepth) {
    let index = 0;
    let channel = 0;
    const length = audioBuffer.length;
    const channels = audioBuffer.numberOfChannels;
    let channelData;
    let sample;

    // Clamping samples onto the 16-bit resolution.
    for (index = 0; index < length; ++index) {
        for (channel = 0; channel < channels; ++channel) {
            channelData = audioBuffer.getChannelData(channel);

            // Branches upon the requested bit depth
            if (bitDepth === 16) {
                sample = channelData[index] * 32768.0;
                if (sample < -32768) {
                    sample = -32768;
                } else if (sample > 32767) {
                    sample = 32767;
                }
                _writeInt16ToArray(sample, targetArray, offset);
                offset += 2;
            } else if (bitDepth === 32) {
                // This assumes we're going to out 32-float, not 32-bit linear.
                sample = _floatBits(channelData[index]);
                _writeInt32ToArray(sample, targetArray, offset);
                offset += 4;
            } else {
                console.log('Invalid bit depth for PCM encoding.');
                return;
            }
        }
    }
}

/**
 * [createWaveFileBlobFromAudioBuffer description]
 * @param  {AudioBuffer} audioBuffer
 * @param  {Boolean} as32BitFloat
 * @return {Blob} Resulting binary blob.
 */
function _createWaveFileBlobFromAudioBuffer(audioBuffer, as32BitFloat) {
    // Encoding setup.
    const frameLength = audioBuffer.length;
    const numberOfChannels = audioBuffer.numberOfChannels;
    const sampleRate = audioBuffer.sampleRate;
    const bitsPerSample = as32BitFloat ? 32 : 16;
    const bytesPerSample = bitsPerSample / 8;
    const byteRate = (sampleRate * numberOfChannels * bitsPerSample) / 8;
    const blockAlign = (numberOfChannels * bitsPerSample) / 8;
    const wavDataByteLength = frameLength * numberOfChannels * bytesPerSample;
    const headerByteLength = 44;
    const totalLength = headerByteLength + wavDataByteLength;
    const waveFileData = new Uint8Array(totalLength);
    const subChunk1Size = 16;
    const subChunk2Size = wavDataByteLength;
    const chunkSize = 4 + (8 + subChunk1Size) + (8 + subChunk2Size);

    _writeStringToArray('RIFF', waveFileData, 0);
    _writeInt32ToArray(chunkSize, waveFileData, 4);
    _writeStringToArray('WAVE', waveFileData, 8);
    _writeStringToArray('fmt ', waveFileData, 12);

    // SubChunk1Size (4)
    _writeInt32ToArray(subChunk1Size, waveFileData, 16);
    // AudioFormat (2): 3 means 32-bit float, 1 means integer PCM.
    _writeInt16ToArray(as32BitFloat ? 3 : 1, waveFileData, 20);
    // NumChannels (2)
    _writeInt16ToArray(numberOfChannels, waveFileData, 22);
    // SampleRate (4)
    _writeInt32ToArray(sampleRate, waveFileData, 24);
    // ByteRate (4)
    _writeInt32ToArray(byteRate, waveFileData, 28);
    // BlockAlign (2)
    _writeInt16ToArray(blockAlign, waveFileData, 32);
    // BitsPerSample (4)
    _writeInt32ToArray(bitsPerSample, waveFileData, 34);
    _writeStringToArray('data', waveFileData, 36);
    // SubChunk2Size (4)
    _writeInt32ToArray(subChunk2Size, waveFileData, 40);

    // Write actual audio data starting at offset 44.
    _writeAudioBufferToArray(audioBuffer, waveFileData, 44, bitsPerSample);

    return new Blob([waveFileData], {
        type: 'audio/wave'
    });
}

/**
 * [createLinkFromAudioBuffer description]
 * @param  {[type]} audioBuffer   [description]
 * @param  {Boolean} as32BitFloat
 * @return {String} file url
 */
function createLinkFromAudioBuffer(audioBuffer, as32BitFloat) {
    const blob = _createWaveFileBlobFromAudioBuffer(audioBuffer, as32BitFloat);
    return window.URL.createObjectURL(blob);
}


window.AudioRecorder = AudioRecorder;
