// =====================================================
// AI Motion Platform API Client
// =====================================================

class MotionAPI {

    constructor() {

        this.baseUrl =
            CONFIG.API_BASE_URL +
            CONFIG.API_PREFIX;

    }

    async createAssessment(videoFile) {

        const formData = new FormData();

        formData.append(
            "assessment_type",
            "footwork"
        );

        formData.append(
            "video",
            videoFile
        );

        const response = await fetch(

            `${this.baseUrl}/motion-assessments`,

            {

                method: "POST",

                body: formData

            }

        );

        if (!response.ok) {

            throw new Error(

                "Upload failed."

            );

        }

        return await response.json();

    }

    async getAssessmentStatus(

        assessmentId

    ) {

        const response = await fetch(

            `${this.baseUrl}/motion-assessments/${assessmentId}`

        );

        if (!response.ok) {

            throw new Error(

                "Status request failed."

            );

        }

        return await response.json();

    }

    async getReport(

        assessmentId

    ) {

        const response = await fetch(

            `${this.baseUrl}/motion-assessments/${assessmentId}/report`

        );

        if (!response.ok) {

            throw new Error(

                "Report request failed."

            );

        }

        return await response.json();

    }

}

const motionAPI = new MotionAPI();