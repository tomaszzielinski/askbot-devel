def get_object_comments(self):
    comments = self.comments.all().order_by('id')
    return comments

def post_get_last_update_info(self):
        when = self.added_at
        who = self.author
        if self.last_edited_at and self.last_edited_at > when:
            when = self.last_edited_at
            who = self.last_edited_by
        comments = self.comments.all()
        if len(comments) > 0:
            for c in comments:
                if c.added_at > when:
                    when = c.added_at
                    who = c.user
        return when, who